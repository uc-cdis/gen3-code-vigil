import pytest

from utils import logger

from pages.login import LoginPage
from pages.gwas import GWASPage


@pytest.mark.argo_wrapper
class TestArgoWrapper(object):
    login_page = LoginPage()
    gwas_page = GWASPage()

    def test_submit_workflow_1(self, page):
        """
        Scenario: Submit workflow Continuous Outcome - Continuous Covariate Phenotype
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="krishnaa@uchicago.edu")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project2")
        self.gwas_page.goto_gwas_ui_app_page(page)
