import io
import tarfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from rapyuta_io_sdk_v2.charts import (
    AsyncChartRepository,
    ChartError,
    ChartRepository,
    branch_repository_url,
)
from rapyuta_io_sdk_v2.config import Configuration


def configuration():
    return Configuration(load_cli_config=False, features={"apply": True, "charts": True})


def archive(entries=None):
    content = io.BytesIO()
    if entries is None:
        entries = {
            "demo/values.yaml": b"name: default\nnested:\n  preserved: yes\n",
            "demo/templates/role.yaml": b"kind: Role\nmetadata:\n  name: '{{ name }}'\nspec: {}\n",
        }
    with tarfile.open(fileobj=content, mode="w:gz") as output:
        for name, value in entries.items():
            member = tarfile.TarInfo(name)
            if isinstance(value, bytes):
                member.size = len(value)
                output.addfile(member, io.BytesIO(value))
            else:
                member.type = tarfile.SYMTYPE
                member.linkname = value
                output.addfile(member)
    return content.getvalue()


INDEX = b"entries:\n  demo:\n    - name: demo\n      version: v2\n      urls: ['demo-v2.tgz']\n    - name: demo\n      version: v1\n      urls: ['demo-v1.tgz']\n"


def http_client(content=None):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            content=INDEX
            if request.url.path.endswith("index.yaml")
            else content or archive(),
        )

    return httpx.Client(transport=httpx.MockTransport(respond)), calls


def test_index_versions_relative_urls_values_and_cleanup():
    transport, calls = http_client()
    with ChartRepository(
        configuration(), "https://repo.test/incubator/index.yaml", transport=transport
    ) as repository:
        with repository.find("demo") as chart:
            assert chart.metadata.version == "v2"
            c = SimpleNamespace(
                config=configuration(),
                create_role=Mock(side_effect=lambda resource, *, context=None: resource),
            )
            rendered = chart.render(c, values={"name": "override"})
            assert rendered[0].metadata.name == "override"
            path = chart.path
            assert path.exists()
            assert chart.apply(c).successful
            assert calls[-1] == "https://repo.test/incubator/demo-v2.tgz"
        assert not path.exists()
        assert repository.find("demo:v1").metadata.version == "v1"
        with pytest.raises(ChartError, match="not found"):
            repository.find("demo", "missing")
    assert not transport.is_closed
    transport.close()


def test_branch_repository_convention():
    assert (
        branch_repository_url("feat/a b")
        == "https://chartsbranch.blob.core.windows.net/charts-per-branch/feat/a%20b/incubator/index.yaml"
    )
    with pytest.raises(ChartError):
        branch_repository_url("../unsafe")


@pytest.mark.parametrize(
    "entries",
    [
        {"../escaped": b"bad"},
        {"/tmp/escaped": b"bad"},
        {"demo/templates/link": "../../escape"},
        {"demo\\escape": b"bad"},
        {"D:/outside": b"bad"},
        {"C:relative-drive": b"bad"},
    ],
)
def test_rejects_archive_paths_and_links_and_cleans(entries):
    transport, _ = http_client(archive(entries))
    with ChartRepository(
        configuration(), "https://repo.test/index.yaml", transport=transport
    ) as repository:
        chart = repository.find("demo")
        with pytest.raises(ChartError):
            chart.download()
        assert chart.path is None
        assert chart._temporary is None
    transport.close()


def test_http_failure_and_checksum_are_checked():
    transport = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(404))
    )
    with ChartRepository(configuration(), transport=transport) as repository:
        with pytest.raises(httpx.HTTPStatusError):
            repository.index()
    transport.close()
    transport, _ = http_client()
    with ChartRepository(configuration(), transport=transport) as repository:
        chart = repository.find("demo")
        chart.metadata.digest = "0" * 64
        with pytest.raises(ChartError, match="checksum"):
            chart.download()
        assert chart._temporary is None
    transport.close()


@pytest.mark.asyncio
async def test_async_download_render_apply_and_cleanup():
    calls = []

    async def respond(request):
        calls.append(str(request.url))
        return httpx.Response(
            200, content=INDEX if request.url.path.endswith("index.yaml") else archive()
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        async with AsyncChartRepository(
            configuration(), "https://repo.test/incubator/index.yaml", transport=transport
        ) as repository:
            async with await repository.find("demo:v1") as chart:
                client = SimpleNamespace(
                    config=configuration(),
                    create_role=AsyncMock(
                        side_effect=lambda resource, *, context=None: resource
                    ),
                )
                report = await chart.apply(client, values={"name": "async"})
                assert report.successful
                client.create_role.assert_awaited_once()
                assert client.create_role.call_args.args[0].metadata.name == "async"
                path = chart.path
            assert not path.exists()
        assert not transport.is_closed
    assert calls[-1] == "https://repo.test/incubator/demo-v1.tgz"
