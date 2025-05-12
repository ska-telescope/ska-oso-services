from unittest import mock
from ska_oso_services.pht.utils.s3_bucket import (
    PRESIGNED_URL_EXPIRY_TIME,
    S3Config,
    S3Method,
    create_presigned_url_delete_pdf,
    create_presigned_url_download_pdf,
    create_presigned_url_upload_pdf,
    generate_presigned_url,
    get_aws_client,
)

class TestS3BucketUtils:

    def test_get_aws_client_returns_boto3_client(self):
        client = get_aws_client()
        assert client.meta.service_model.service_name == "s3"

    @mock.patch("boto3.client")
    def test_get_aws_client_invokes_boto3(self, mock_boto_client):
        get_aws_client()
        mock_boto_client.assert_called_once()

    def test_generate_presigned_url_calls_client(self):
        fake_client = mock.Mock()
        config = S3Config(bucket="test-bucket", expiry=120)
        generate_presigned_url("file.pdf", S3Method.PUT, fake_client, config)
        fake_client.generate_presigned_url.assert_called_once_with(
            ClientMethod="put_object",
            Params={"Bucket": "test-bucket", "Key": "file.pdf"},
            ExpiresIn=120,
        )

    def test_create_presigned_url_upload_pdf_delegates(self):
        mock_client = mock.Mock()
        create_presigned_url_upload_pdf("upload.pdf", mock_client)
        mock_client.generate_presigned_url.assert_called_once()

    def test_create_presigned_url_download_pdf_delegates(self):
        mock_client = mock.Mock()
        create_presigned_url_download_pdf("download.pdf", mock_client)
        mock_client.generate_presigned_url.assert_called_once()

    def test_create_presigned_url_delete_pdf_delegates(self):
        mock_client = mock.Mock()
        create_presigned_url_delete_pdf("delete.pdf", mock_client)
        mock_client.generate_presigned_url.assert_called_once()
