import platform
import subprocess

SERVICE_NAME = "personal-ai-knowledge-butler"
ACCOUNT_NAME = "openai-api-key"


class SecretStoreError(RuntimeError):
    pass


def is_keychain_available() -> bool:
    return platform.system() == "Darwin"


def save_openai_api_key(api_key: str) -> None:
    if not api_key:
        return
    if not is_keychain_available():
        raise SecretStoreError("Encrypted API key storage currently requires macOS Keychain.")
    delete_openai_api_key(ignore_missing=True)
    command = [
        "security",
        "add-generic-password",
        "-a",
        ACCOUNT_NAME,
        "-s",
        SERVICE_NAME,
        "-w",
        api_key,
        "-U",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise SecretStoreError(result.stderr.strip() or "Failed to save API key to Keychain.")


def load_openai_api_key() -> str:
    if not is_keychain_available():
        return ""
    command = [
        "security",
        "find-generic-password",
        "-a",
        ACCOUNT_NAME,
        "-s",
        SERVICE_NAME,
        "-w",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def delete_openai_api_key(ignore_missing: bool = False) -> None:
    if not is_keychain_available():
        return
    command = [
        "security",
        "delete-generic-password",
        "-a",
        ACCOUNT_NAME,
        "-s",
        SERVICE_NAME,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 and not ignore_missing:
        raise SecretStoreError(result.stderr.strip() or "Failed to delete API key from Keychain.")
