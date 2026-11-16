from unittest import mock
from urllib.parse import urlsplit

import pytest
import requests
from astropy.table import MaskedColumn, Table
from astropy.units import Quantity
from astroquery.exceptions import RemoteServiceError, TableParseError
from astroquery.simbad import SimbadClass
from pyvo.dal.exceptions import DALAccessError, DALServiceError
from ska_oso_pdm import GalacticCoordinates, ICRSCoordinates, RadialVelocity, Target

from ska_oso_services.common.coordinateslookup import (
    CATALOGUE_TIMEOUT_S,
    SIMBAD_SERVERS,
    Catalogue,
    CatalogueUnavailableError,
    ReferenceFrame,
    _simbad_client,
    _TimeoutHTTPAdapter,
    get_catalogue_lookup,
    get_coordinates,
    lookup_in_ned,
    lookup_in_simbad,
)
from ska_oso_services.common.error_handling import CatalogLookupError, NotFoundError

MODULE = "ska_oso_services.common.coordinateslookup"

SIMBAD_RESULT_WITH_VELOCITY = Table(
    {
        "ra": [204.25383],
        "dec": [-29.865761111111112],
        "rvz_type": ["v"],
        "rvz_radvel": [519.1],
        "rvz_redshift": [0.0017330329174689574],
    }
)
SIMBAD_RESULT_WITH_REDSHIFT = Table(
    {
        "ra": [204.25383],
        "dec": [-29.865761111111112],
        "rvz_type": ["z"],
        "rvz_radvel": [519.1],
        "rvz_redshift": [0.0017330329174689574],
    }
)
EMPTY_SIMBAD_RESULT = Table(names=("ra", "dec", "rvz_type", "rvz_radvel", "rvz_redshift"))

NED_RESULT = Table({"RA": [204.25396], "DEC": [-29.86542], "Redshift": [0.001711]})
NED_RESULT_WITHOUT_REDSHIFT = Table(
    {"RA": [204.25396], "DEC": [-29.86542], "Redshift": MaskedColumn([0.0], mask=[True])}
)
NED_NOT_FOUND_ERROR = RemoteServiceError(
    "The remote service returned the following error message.\nERROR: The object name that "
    "you have submitted is not currently recognized by the NED name interpreter."
)

SIMBAD_ICRS_COORDINATES = ICRSCoordinates(ra_str="13:37:00.9192", dec_str="-29:51:56.740")
NED_ICRS_COORDINATES = ICRSCoordinates(ra_str="13:37:00.9504", dec_str="-29:51:55.512")

TEST_TARGET_WITH_VELOCITY = Target(
    name="M83",
    reference_coordinate=SIMBAD_ICRS_COORDINATES,
    radial_velocity=RadialVelocity(quantity=Quantity(value=519.1, unit="km/s")),
)
TEST_NED_TARGET_WITH_REDSHIFT = Target(
    name="M83",
    reference_coordinate=NED_ICRS_COORDINATES,
    radial_velocity=RadialVelocity(redshift=0.001711),
)


@pytest.fixture(name="simbad_clients")
def fixture_simbad_clients():
    """Mock SIMBAD clients for the CDS server and the Harvard mirror, in that order"""
    clients = (mock.MagicMock(), mock.MagicMock())
    clients_by_server = dict(zip(SIMBAD_SERVERS, clients))
    with mock.patch(f"{MODULE}._simbad_client", side_effect=clients_by_server.__getitem__):
        yield clients


@pytest.fixture(name="ned")
def fixture_ned():
    with mock.patch(f"{MODULE}.Ned") as ned:
        yield ned


@pytest.fixture(name="sent_requests")
def fixture_sent_requests():
    """
    Fail every HTTP request as though it timed out, recording the URL and timeout
    each was sent with, so the real SIMBAD client can be used offline.
    """
    sent = []

    def send(request, timeout=None, **_):
        sent.append((request.url, timeout))
        raise requests.ConnectTimeout(f"Connection to {request.url} timed out")

    with mock.patch("requests.adapters.HTTPAdapter.send", side_effect=send):
        yield sent


def test_found_in_simbad(simbad_clients, ned):
    cds, harvard = simbad_clients
    cds.query_object.return_value = SIMBAD_RESULT_WITH_VELOCITY

    result = get_coordinates("M83", ReferenceFrame.equatorial)

    assert result == TEST_TARGET_WITH_VELOCITY
    # One request in total: the position and velocity come from the same query
    cds.query_object.assert_called_once()
    harvard.query_object.assert_not_called()
    ned.query_object.assert_not_called()


@pytest.mark.parametrize("rvz_type", ["z", "c"])
def test_found_in_simbad_with_redshift(simbad_clients, ned, rvz_type):
    # SIMBAD stores a cz measurement ("c") as its redshift too
    cds, _ = simbad_clients
    simbad_result = SIMBAD_RESULT_WITH_REDSHIFT.copy()
    simbad_result["rvz_type"] = [rvz_type]
    cds.query_object.return_value = simbad_result

    result = get_coordinates("M83", ReferenceFrame.equatorial)

    assert result.radial_velocity == RadialVelocity(redshift=0.0017330329174689574)


def test_found_in_simbad_galactic(simbad_clients, ned):
    cds, _ = simbad_clients
    cds.query_object.return_value = SIMBAD_RESULT_WITH_VELOCITY

    result = get_coordinates("M83", ReferenceFrame.galactic)

    assert result.reference_coordinate == GalacticCoordinates(l=314.5835776, b=31.9726999)


def test_not_found_in_simbad_found_in_ned(simbad_clients, ned):
    cds, harvard = simbad_clients
    cds.query_object.return_value = EMPTY_SIMBAD_RESULT
    ned.query_object.return_value = NED_RESULT

    result = get_coordinates("M83", ReferenceFrame.equatorial)

    assert result == TEST_NED_TARGET_WITH_REDSHIFT
    # The mirror is only for when CDS can't be reached, not for objects it doesn't have
    harvard.query_object.assert_not_called()


def test_found_in_ned_without_redshift(simbad_clients, ned):
    cds, _ = simbad_clients
    cds.query_object.return_value = EMPTY_SIMBAD_RESULT
    ned.query_object.return_value = NED_RESULT_WITHOUT_REDSHIFT

    result = get_coordinates("M83", ReferenceFrame.equatorial)

    assert result.radial_velocity == RadialVelocity(redshift=0)


def test_not_found_in_simbad_or_ned(simbad_clients, ned):
    cds, _ = simbad_clients
    cds.query_object.return_value = EMPTY_SIMBAD_RESULT
    ned.query_object.side_effect = NED_NOT_FOUND_ERROR

    with pytest.raises(NotFoundError) as err:
        get_coordinates("dummy name", ReferenceFrame.equatorial)

    assert (
        err.value.detail == "Object dummy name not found in SIMBAD or NED. "
        "Please try again or manually input target details."
    )


@pytest.mark.parametrize(
    "error",
    [
        DALServiceError("Connection failed"),
        requests.ConnectTimeout("Connection to simbad.cds.unistra.fr timed out"),
    ],
)
def test_simbad_cds_unavailable_uses_harvard_mirror(simbad_clients, ned, error):
    cds, harvard = simbad_clients
    cds.query_object.side_effect = error
    harvard.query_object.return_value = SIMBAD_RESULT_WITH_VELOCITY

    result = get_coordinates("M83", ReferenceFrame.equatorial)

    assert result == TEST_TARGET_WITH_VELOCITY
    ned.query_object.assert_not_called()


def test_simbad_unavailable_found_in_ned(simbad_clients, ned):
    for client in simbad_clients:
        client.query_object.side_effect = DALServiceError("Connection failed")
    ned.query_object.return_value = NED_RESULT

    result = get_coordinates("M83", ReferenceFrame.equatorial)

    assert result == TEST_NED_TARGET_WITH_REDSHIFT


def test_simbad_unavailable_not_found_in_ned(simbad_clients, ned):
    for client in simbad_clients:
        client.query_object.side_effect = DALServiceError("Connection failed")
    ned.query_object.side_effect = NED_NOT_FOUND_ERROR

    # The object may be in SIMBAD, so this isn't reported as not found
    with pytest.raises(CatalogLookupError) as err:
        get_coordinates("dummy name", ReferenceFrame.equatorial)

    assert (
        err.value.detail == "Unable to look up dummy name as SIMBAD could not be reached. "
        "Please try again later or manually input target details."
    )


@pytest.mark.parametrize(
    "error",
    [
        RemoteServiceError("The remote service returned an error, but with no message."),
        TableParseError("Failed to parse NED result!"),
        requests.ReadTimeout("Read timed out."),
    ],
)
def test_ned_unavailable_not_found_in_simbad(simbad_clients, ned, error):
    cds, _ = simbad_clients
    cds.query_object.return_value = EMPTY_SIMBAD_RESULT
    ned.query_object.side_effect = error

    with pytest.raises(CatalogLookupError) as err:
        get_coordinates("dummy name", ReferenceFrame.equatorial)

    assert "as NED could not be reached" in err.value.detail


def test_all_catalogues_unavailable(simbad_clients, ned):
    for client in simbad_clients:
        client.query_object.side_effect = DALServiceError("Connection failed")
    ned.query_object.side_effect = requests.ConnectionError("Connection refused")

    with pytest.raises(CatalogLookupError) as err:
        get_coordinates("dummy name", ReferenceFrame.equatorial)

    assert "as SIMBAD or NED could not be reached" in err.value.detail


def test_only_given_catalogues_are_queried(simbad_clients, ned):
    ned.query_object.return_value = NED_RESULT

    result = get_coordinates("M83", ReferenceFrame.equatorial, catalogues=[Catalogue.ned])

    assert result == TEST_NED_TARGET_WITH_REDSHIFT
    for client in simbad_clients:
        client.query_object.assert_not_called()


@pytest.mark.parametrize(
    "catalogue, expected_lookup",
    [(Catalogue.simbad, lookup_in_simbad), (Catalogue.ned, lookup_in_ned)],
)
def test_get_catalogue_lookup(catalogue, expected_lookup):
    assert get_catalogue_lookup(catalogue) is expected_lookup


def test_simbad_client_setup_requests_time_out(sent_requests):
    # Use the real clients, whose setup makes requests before the lookup is sent
    _simbad_client.cache_clear()

    with pytest.raises(CatalogueUnavailableError):
        lookup_in_simbad("M83")

    assert {urlsplit(url).hostname for url, _ in sent_requests} == set(SIMBAD_SERVERS)
    assert all(timeout == CATALOGUE_TIMEOUT_S for _, timeout in sent_requests)


# Skip the requests made while setting up the client so only the lookup's query is sent
@mock.patch.object(SimbadClass, "hardlimit", 10000)
@mock.patch.object(SimbadClass, "add_votable_fields")
def test_simbad_query_times_out(mock_add_votable_fields, sent_requests):
    # Call the uncached function so the client isn't kept for other tests
    client = _simbad_client.__wrapped__("simbad.harvard.edu")

    with pytest.raises((DALAccessError, requests.RequestException)):
        client.query_object("M83")

    mock_add_votable_fields.assert_called_once_with("velocity")
    assert sent_requests == [
        ("https://simbad.harvard.edu/simbad/sim-tap/sync", CATALOGUE_TIMEOUT_S)
    ]


def test_timeout_adapter_only_sets_missing_timeout():
    with mock.patch("requests.adapters.HTTPAdapter.send") as mock_send:
        _TimeoutHTTPAdapter().send(mock.sentinel.request, timeout=None)
        _TimeoutHTTPAdapter().send(mock.sentinel.request, timeout=60)

    assert mock_send.call_args_list == [
        mock.call(mock.sentinel.request, timeout=CATALOGUE_TIMEOUT_S),
        mock.call(mock.sentinel.request, timeout=60),
    ]
