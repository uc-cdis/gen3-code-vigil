"""
SHEEPDOG & PEREGRINE SERVICE
"""
import os
import pytest

from cdislogging import get_logger

from utils import nodes
from services.sheepdog_peregrine import SheepdogPeregrine

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.sheepdog
@pytest.mark.peregrine
class TestSheepdogPeregrineService:
    def test_get_all_nodes(self):
        sdp = SheepdogPeregrine()
        sdp.addNode(nodes.ithNodeInPath(1), "main_account")
