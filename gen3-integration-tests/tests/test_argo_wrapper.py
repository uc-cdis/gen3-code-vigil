import pandas as pd
import pytest
from pages.gwas import GWASPage
from pages.login import LoginPage
from playwright.sync_api import expect
from utils import logger
from utils.test_execution import screenshot


@pytest.mark.skipif(
    "argo-wrapper" not in pytest.deployed_services,
    reason="argo-wrapper service is not running on this environment",
)
@pytest.mark.argo_wrapper
@pytest.mark.wip
class TestArgoWrapper(object):
    login_page = LoginPage()
    gwas_page = GWASPage()
    submitted_jobs = {}  # key: job_name, value: job_id

    def test_submit_workflow_1(self, page):
        """
        Scenario: Submit workflow Continuous Outcome - Continuous Covariate Phenotype
        Steps:
            1. Login with main_account user (user has access to gwas projects)
            2. Check the monthly workflow limits of the user
            3. Submit a Continuous Outcome - Continuous Covariate Phenotype workflows
            4. Verify the workflow is submitted successfully and monthly workflow limit is increased by 1
            5. Also verify the monthly workflow limits are same on GWAS results page
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        workflow_submitted, workflow_limit = self.gwas_page.get_workflow_limits(page)
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
        self.gwas_page.validate_workflow_limits_after_workflow_submission(
            page, workflow_submitted, workflow_limit
        )
        self.gwas_page.verify_job_submission(page)

    def test_submit_workflow_2(self, page):
        """
        Scenario: Submit workflow Continuous Outcome - Dichotomous Covariate Phenotype
        Steps:
            1. Login with main_account user (user has access to gwas projects)
            2. Check the monthly workflow limits of the user
            3. Submit a Continuous Outcome - Dichotomous Covariate Phenotype workflows
            4. Verify the workflow is submitted successfully and monthly workflow limit is increased by 1
            5. Also verify the monthly workflow limits are same on GWAS results page
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        workflow_submitted, workflow_limit = self.gwas_page.get_workflow_limits(page)
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
        self.gwas_page.validate_workflow_limits_after_workflow_submission(
            page, workflow_submitted, workflow_limit
        )
        self.gwas_page.verify_job_submission(page)

    def test_submit_workflow_3(self, page):
        """
        Scenario: Submit workflow Dichotomous Outcome - Continuous Covariate Phenotype
        Steps:
            1. Login with main_account user (user has access to gwas projects)
            2. Check the monthly workflow limits of the user
            3. Submit a Dichotomous Outcome - Continuous Covariate Phenotype workflows
            4. Verify the workflow is submitted successfully and monthly workflow limit is increased by 1
            5. Also verify the monthly workflow limits are same on GWAS results page
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        workflow_submitted, workflow_limit = self.gwas_page.get_workflow_limits(page)
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
        self.gwas_page.validate_workflow_limits_after_workflow_submission(
            page, workflow_submitted, workflow_limit
        )
        self.gwas_page.verify_job_submission(page)

    def test_submit_workflow_4(self, page):
        """
        Scenario: Submit workflow Dichotomous Outcome - Dichotomous Covariate Phenotype
        Steps:
            1. Login with main_account user (user has access to gwas projects)
            2. Check the monthly workflow limits of the user
            3. Submit a Dichotomous Outcome - Dichotomous Covariate Phenotype workflows
            4. Verify the workflow is submitted successfully and monthly workflow limit is increased by 1
            5. Also verify the monthly workflow limits are same on GWAS results page
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="main_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        workflow_submitted, workflow_limit = self.gwas_page.get_workflow_limits(page)
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
        self.gwas_page.validate_workflow_limits_after_workflow_submission(
            page, workflow_submitted, workflow_limit
        )
        self.gwas_page.verify_job_submission(page)

    def test_gwas_result_app(self, page):
        """
        Scenario: GWAS Result App
        Steps:
            1. For all the workflows submitted, get the status of workflows
            2. Verify the workflows are in "succeeded" state (Waits upto 10mins for checking workflow status)
        """
        workflows_data = self.gwas_page.get_all_workflows(project="project1")
        df = pd.DataFrame(workflows_data)
        for job_name, job_id in self.submitted_jobs.items():
            workflow_df = df[df["wf_name"] == job_name]
            uid_value = workflow_df["uid"].iloc[0]
            assert self.gwas_page.check_job_result(
                uid_value, job_id
            ), f"Workflow {job_id} failed/errored"

    def test_next_previous_buttons_gwas_page(self, page):
        """
        Scenario: Test next and previous buttons GWAS page
        Steps:
            1. Login with main_account user (user has access to gwas projects)
            2. Perform steps to submit a workflow, but don't actuall submit it on the last step
            3. Navigate back and forth between workflow submission steps using Previous and Next buttons
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="main_account")

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
            1. Login with smarty_two user (user has access to gwas but not gwas projects)
            2. Goto Analysis page and verify a pop up is displayed stating user doesn't have access
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="smarty_two")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.unauthorized_user_select_team_project(page)

    def test_workflow_submission_after_workflow_limit_reached(self, page):
        """
        Scenario: Workflow submission is disabled once monthly workflow limit is reached
        Steps:
            1. Login with indexing_account user (user has access to gwas projects and has reached its monthly workflow limit)
            2. Submit a new workflow
            3. On the last step of submitting the workflow, an error message should be displayed that user has already reached
               the monthly workflow limit and the Submit button should be disabled.
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="indexing_account")

        # Perform operations on GWAS Page
        self.gwas_page.goto_analysis_page(page)
        self.gwas_page.select_team_project(page, project_name="project1")
        self.gwas_page.goto_gwas_ui_app_page(page)
        workflow_submitted, workflow_limit = self.gwas_page.get_workflow_limits(page)
        logger.info(f"Number of Workflows submitted: {workflow_submitted}")
        logger.info(f"Monthly Workflows limit: {workflow_limit}")
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
        self.gwas_page.submit_workflow_after_monthly_limit_reached(page)
