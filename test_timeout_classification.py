#!/usr/bin/env python3
"""Test that timeout errors are classified as unauthorized"""

from tfsmcp.contracts import CommandResult
from tfsmcp.tfs.classifier import TfOutputClassifier


def test_timeout_classification():
    classifier = TfOutputClassifier()
    
    # Simulate timeout error
    timeout_result = CommandResult(
        command=["tf.exe", "info", "D:\\TFS_DevOps\\SPF\\develop-pgp-30745"],
        exit_code=1,
        stdout="",
        stderr="Command 'tf.exe info D:\\TFS_DevOps\\SPF\\develop-pgp-30745' timed out after 120 seconds",
        category="raw",
    )
    
    category = classifier.classify(timeout_result)
    
    print(f"Timeout error classification: {category}")
    assert category == "unauthorized", f"Expected 'unauthorized', got '{category}'"
    print("✓ Timeout is correctly classified as unauthorized")


def test_explicit_auth_error():
    classifier = TfOutputClassifier()
    
    # Explicit auth error
    auth_result = CommandResult(
        command=["tf.exe", "info", "test"],
        exit_code=1,
        stdout="",
        stderr="TF30063: You are not authorized to access https://dev.azure.com/ED-ProjetoSoftware.",
        category="raw",
    )
    
    category = classifier.classify(auth_result)
    
    print(f"Auth error classification: {category}")
    assert category == "unauthorized", f"Expected 'unauthorized', got '{category}'"
    print("✓ Explicit auth error is correctly classified")


def test_portuguese_auth_error():
    classifier = TfOutputClassifier()
    
    # Portuguese auth error
    auth_result = CommandResult(
        command=["tf.exe", "info", "test"],
        exit_code=1,
        stdout="",
        stderr="Você não está autorizado a acessar este recurso.",
        category="raw",
    )
    
    category = classifier.classify(auth_result)
    
    print(f"Portuguese auth error classification: {category}")
    assert category == "unauthorized", f"Expected 'unauthorized', got '{category}'"
    print("✓ Portuguese auth error is correctly classified")


if __name__ == "__main__":
    test_timeout_classification()
    test_explicit_auth_error()
    test_portuguese_auth_error()
    print("\n✓ All tests passed!")
