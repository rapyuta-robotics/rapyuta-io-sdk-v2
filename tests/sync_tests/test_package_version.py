import pytest
from pydantic import ValidationError

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Deployment, Package
from rapyuta_io_sdk_v2.models.utils import PackageDepends
from tests.data import package_body


def _with_version(body: dict, version) -> dict:
    metadata = {**body["metadata"]}
    if version is _MISSING:
        _ = metadata.pop("version", None)
    else:
        metadata["version"] = version
    return {**body, "metadata": metadata}


class _Missing:
    pass


_MISSING = _Missing()


def test_package_accepts_a_concrete_version(package_body):
    package = Package.model_validate(_with_version(package_body, "v1.0.0"))
    assert package.metadata.version == "v1.0.0"


@pytest.mark.parametrize("version", [_MISSING, None, ""])
def test_package_rejects_a_missing_or_empty_version(package_body, version):
    # A Package is identified by (name, version). An absent, null or empty
    # version makes two distinct versions indistinguishable to any consumer
    # that keys on that pair.
    with pytest.raises(ValidationError) as exc:
        _ = Package.model_validate(_with_version(package_body, version))

    assert "version" in str(exc.value)


def test_package_depends_accepts_a_concrete_version():
    depends = PackageDepends.model_validate(
        {"kind": "package", "nameOrGUID": "test-package", "version": "v1.0.0"}
    )
    assert depends.version == "v1.0.0"


@pytest.mark.parametrize("version", [None, ""])
def test_package_depends_rejects_a_missing_or_empty_version(version):
    # Templated manifests render an empty string when the value is not
    # supplied, so the empty case is reachable without an unusual manifest.
    with pytest.raises(ValidationError) as exc:
        _ = PackageDepends.model_validate(
            {"kind": "package", "nameOrGUID": "test-package", "version": version}
        )

    assert "version" in str(exc.value)


def test_deployment_package_dependency_rejects_an_empty_version():
    body = {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "Deployment",
        "metadata": {
            "name": "test-deployment",
            "depends": {"kind": "package", "nameOrGUID": "test-package", "version": ""},
        },
        "spec": {"runtime": "cloud"},
    }

    with pytest.raises(ValidationError) as exc:
        _ = Deployment.model_validate(body)

    assert "version" in str(exc.value)
