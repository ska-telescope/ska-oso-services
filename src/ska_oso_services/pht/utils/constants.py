from os import getenv

# HTML email template
HTML_TEMPLATE = """
<html>
<body>
    <p>SKAO proposal with ID <strong>{{ prsl_id }}</strong>.</p>
    <p><a href="{{ link }}">Click here</a> to accept or reject the invitation.</p>
</body>
</html>
"""


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
    "info": {
        "title": "The Milky Way View",
        "proposal_type": {
            "main_type": "standard_proposal",
            "attributes": ["coordinated_proposal"],
        },
    },
}

ACCESS_ID = "access_id"
PRSL_ID = "prsl_id"
SV_NAME = "Science Verification"
TENANT_ID = "78887040-bad7-494b-8760-88dcacfb3805"
CLIENT_ID = "e4d6bb9b-cdd0-46c4-b30a-d045091b501b"
CLIENT_SECRET = getenv("OSO_CLIENT_SECRET", "OSO_CLIENT_SECRET")
SCOPE = ["https://graph.microsoft.com/.default"]
MS_GRAPH_URL = "https://graph.microsoft.com/v1.0"
