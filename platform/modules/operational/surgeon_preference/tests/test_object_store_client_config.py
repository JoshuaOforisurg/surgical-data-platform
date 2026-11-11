from types import SimpleNamespace
from unittest.mock import MagicMock

import boto3

from storage.object_store import S3ObjectStoreClient


def test_s3_client_uses_bounded_network_timeouts_and_retries(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(boto3, "client", MagicMock(return_value=client))
    settings = SimpleNamespace(
        endpoint="http://localhost:9000",
        access_key="test-user",
        secret_key="test-secret",
        bucket="test-bucket",
        secure=False,
    )

    S3ObjectStoreClient(settings)

    config = boto3.client.call_args.kwargs["config"]
    assert config.connect_timeout == 5
    assert config.read_timeout == 30
    assert config.retries == {"mode": "standard", "max_attempts": 2}
