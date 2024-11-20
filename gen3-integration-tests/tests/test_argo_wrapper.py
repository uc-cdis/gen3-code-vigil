import pytest
from pages.gwas import GWASPage
from pages.login import LoginPage
from playwright.sync_api import expect
from utils import logger
from utils.test_execution import screenshot


@pytest.mark.argo_wrapper
class TestArgoWrapper(object):
    login_page = LoginPage()
    gwas_page = GWASPage()
    submitted_jobs = {}  # key: job_name, value: job_id

    def test_submit_workflow_1(self, page):
        """
        Scenario: Submit workflow Continuous Outcome - Continuous Covariate Phenotype
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        self.gwas_page.select_cohort(page)
        self.gwas_page.attrition_table(page)
        self.gwas_page.click_next_button(page)

        # Selecting Continuous Phenotype
        self.gwas_page.select_continuous_phenotype(page)
        self.gwas_page.select_continuous_phenotype_concept(page)
        self.gwas_page.click_submit_button(page)

        # Select Continuous Covariate
        self.gwas_page.select_continuous_covariate(page)
        self.gwas_page.select_first_concept(page)
        self.gwas_page.click_add_button(page)
        self.gwas_page.select_continuous_covariate(page)
        self.gwas_page.select_second_concept(page)
        self.gwas_page.click_add_button(page)
        screenshot(page, "Continuous-ContinuousCovariate")
        self.gwas_page.click_next_button(page)

        # Selecting Ancestry
        self.gwas_page.select_ancestry(page)
        self.gwas_page.click_next_button(page)

        # Submit the workflow
        job_name, job_id = self.gwas_page.submit_workflow(page)
        self.submitted_jobs[job_name] = job_id
        self.gwas_page.verify_job_submission(page)

    def test_submit_workflow_2(self, page):
        """
        Scenario: Submit workflow Continuous Outcome - Dichotomous Covariate Phenotype
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        self.gwas_page.select_cohort(page)
        self.gwas_page.attrition_table(page)
        self.gwas_page.click_next_button(page)

        # Selecting Continuous Phenotype
        self.gwas_page.select_continuous_phenotype(page)
        self.gwas_page.select_continuous_phenotype_concept(page)
        self.gwas_page.click_submit_button(page)

        # Select Dichotomous Covariate
        self.gwas_page.select_dichotomous_covariate(page)
        self.gwas_page.select_first_value(page)
        self.gwas_page.select_second_value(page)
        self.gwas_page.enter_phenotype_name(page)
        self.gwas_page.click_add_button(page)
        screenshot(page, "Continuous-DichotomousCovariate")
        self.gwas_page.click_next_button(page)

        # Selecting Ancestry
        self.gwas_page.select_ancestry(page)
        self.gwas_page.click_next_button(page)

        # Submit the workflow
        job_name, job_id = self.gwas_page.submit_workflow(page)
        self.submitted_jobs[job_name] = job_id
        self.gwas_page.verify_job_submission(page)

    def test_submit_workflow_3(self, page):
        """
        Scenario: Submit workflow Dichotomous Outcome - Continuous Covariate Phenotype
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        self.gwas_page.select_cohort(page)
        self.gwas_page.attrition_table(page)
        self.gwas_page.click_next_button(page)

        # Selecting Dichotomous Phenotype
        self.gwas_page.select_dichotomous_phenotype(page)
        self.gwas_page.select_dichotomous_phenotype_concept(page)

        # Select Continuous Covariate
        self.gwas_page.select_continuous_covariate(page)
        self.gwas_page.select_first_concept(page)
        self.gwas_page.click_add_button(page)
        self.gwas_page.select_continuous_covariate(page)
        self.gwas_page.select_second_concept(page)
        self.gwas_page.click_add_button(page)
        screenshot(page, "Dichotomous-ContinuousCovariate")
        self.gwas_page.click_next_button(page)

        # Selecting Ancestry
        self.gwas_page.select_ancestry(page)
        self.gwas_page.click_next_button(page)

        # Submit the workflow
        job_name, job_id = self.gwas_page.submit_workflow(page)
        self.submitted_jobs[job_name] = job_id
        self.gwas_page.verify_job_submission(page)

    def test_submit_workflow_4(self, page):
        """
        Scenario: Submit workflow Dichotomous Outcome - Dichotomous Covariate Phenotype
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        self.gwas_page.select_cohort(page)
        self.gwas_page.attrition_table(page)
        self.gwas_page.click_next_button(page)

        # Selecting Dichotomous Phenotype
        self.gwas_page.select_dichotomous_phenotype(page)
        self.gwas_page.select_dichotomous_phenotype_concept(page)

        # Select Dichotomous Covariate
        self.gwas_page.select_dichotomous_covariate(page)
        self.gwas_page.select_first_value(page)
        self.gwas_page.select_second_value(page)
        self.gwas_page.enter_phenotype_name(page)
        self.gwas_page.click_add_button(page)
        screenshot(page, "Dichotomous-DichotomousCovariate")
        self.gwas_page.click_next_button(page)

        # Selecting Ancestry
        self.gwas_page.select_ancestry(page)
        self.gwas_page.click_next_button(page)

        # Submit the workflow
        job_name, job_id = self.gwas_page.submit_workflow(page)
        self.submitted_jobs[job_name] = job_id
        self.gwas_page.verify_job_submission(page)

    def test_gwas_result_app(self, page):
        """
        Scenario: GWAS Result App
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_result_page(page)
        for job_name, job_id in self.submitted_jobs.items():
            self.gwas_page.check_job_result(page, job_name, job_id)

    def test_next_previous_buttons_gwas_page(self, page):
        """
        Scenario: Test next and previous buttons GWAS page
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        self.gwas_page.select_cohort(page)
        self.gwas_page.attrition_table(page)
        self.gwas_page.click_next_button(page)

        # Click previous button and next button
        self.gwas_page.click_previous_button(page)
        checked_radio = page.locator(self.gwas_page.CHECKED_RADIO)
        expect(checked_radio).to_be_visible(timeout=5000)
        self.gwas_page.click_next_button(page)

        # Selecting Continuous Phenotype
        self.gwas_page.select_continuous_phenotype(page)
        self.gwas_page.select_continuous_phenotype_concept(page)
        self.gwas_page.click_submit_button(page)

        # Click previous button and next button
        self.gwas_page.click_previous_button(page)
        add_coninuous_phenotype = page.locator(self.gwas_page.ADD_CONTINOUOUS_PHENOTYPE)
        expect(add_coninuous_phenotype).to_be_visible(timeout=5000)
        self.gwas_page.click_next_button(page)

        # Select Continuous Covariate
        self.gwas_page.select_continuous_covariate(page)
        self.gwas_page.select_first_concept(page)
        self.gwas_page.click_add_button(page)
        self.gwas_page.click_next_button(page)

        # Selecting Ancestry
        self.gwas_page.select_ancestry(page)
        self.gwas_page.click_next_button(page)
        submit_dialog_box = page.locator(self.gwas_page.SUBMIT_DIALOG_BOX)
        expect(submit_dialog_box).to_be_visible(timeout=5000)
        screenshot(page, "SubmitDialogBox")

    def test_unauthorized_access_to_gwas(self, page):
        """
        Scenario: Unauthorized access to GWAS
        Steps:
            1.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.gwas_page.login(page, user="dummy_one")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.unauthorized_user_select_team_project(page)
