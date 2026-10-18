from streamlit_services import streamlit_service


def test_empty_azure_connection_string_selects_local_minio(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "")
    monkeypatch.setattr(streamlit_service, "MinIOClient", lambda: "minio")
    monkeypatch.setattr(
        streamlit_service, "AzureBlobStorageClient", lambda: "azure"
    )

    assert streamlit_service.get_storage_client() == "minio"


def test_configured_azure_connection_string_selects_azure(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "configured")
    monkeypatch.setattr(streamlit_service, "MinIOClient", lambda: "minio")
    monkeypatch.setattr(
        streamlit_service, "AzureBlobStorageClient", lambda: "azure"
    )

    assert streamlit_service.get_storage_client() == "azure"
