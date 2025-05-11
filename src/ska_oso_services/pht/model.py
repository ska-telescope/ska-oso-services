from pydantic import BaseModel, EmailStr


class EmailRequest(BaseModel):
    """
    Schema for incoming email request.

    Attributes:
        email (EmailStr): The recipient's email address.
        prsl_id (str): The SKAO proposal ID.
    """

    email: EmailStr
    prsl_id: str
