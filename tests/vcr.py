import os
import re

import vcr

THEGRAPH_API_KEY = os.getenv("THEGRAPH_API_KEY", "MOCK_KEY")
RPC_MAINNET_URL = os.getenv("RPC_MAINNET_URL", "MOCK_MAINNET_RPC_URL")
RPC_GNOSIS_URL = os.getenv("RPC_GNOSIS_URL", "MOCK_GNOSIS_RPC_URL")


def scrub_api_keys(request):
    if THEGRAPH_API_KEY in request.path:
        request.uri = request.uri.replace(THEGRAPH_API_KEY, "MOCK_KEY")

    if ".alchemy.com/v2/" in request.uri:
        request.uri = re.sub(r"(/v2/)[^/]+", r"\1", request.uri) + "MOCK_KEY"

    # if RPC_GNOSIS_URL in request.uri:
    #     request.uri = re.sub(r"(/v2/)[^/]+", r"\1", request.uri)

    return request


def transform_path(path: str) -> str:
    suffix = ".yaml"
    if not path.endswith(suffix):
        path = path + suffix

    return path.replace("/tests/", "/tests/fixtures/cassettes/")


my_vcr = vcr.VCR(
    path_transformer=transform_path,
    before_record_request=scrub_api_keys,
)
