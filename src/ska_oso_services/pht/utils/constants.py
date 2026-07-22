from ska_oso_services.settings import get_settings

PANEL_NAME_POOL = [
    "Cosmology",
    "Cradle of Life",
    "Epoch of Re-ionization",
    "Extragalactic continuum",
    "Extragalactic Spectral line",
    "Gravitational Waves",
    "High Energy Cosmic Particles",
    "HI Galaxy science",
    "Magnetism",
    "Our Galaxy",
    "Pulsars",
    "Solar, Heliospheric and Ionospheric Physics",
    "Transients",
    "VLBI",
]


EXAMPLE_PROPOSAL = {
    "prsl_id": "prp-ska01-202204-02",
    "status": "draft",
    "cycle": "5000_2023",
    "proposal_info": {
        "title": "The Milky Way View",
        "proposal_type": {
            "main_type": "standard_proposal",
            "attributes": ["coordinated_proposal"],
        },
    },
    "observation_info": {},
}

ACCESS_ID = "access_id"
PRSL_ID = "prsl_id"
SV_NAME = "Science Verification"
TENANT_ID = "78887040-bad7-494b-8760-88dcacfb3805"
CLIENT_ID = "e4d6bb9b-cdd0-46c4-b30a-d045091b501b"
CLIENT_SECRET = get_settings().auth.client_secret
SCOPE = ["https://graph.microsoft.com/.default"]
MS_GRAPH_URL = "https://graph.microsoft.com/v1.0"
