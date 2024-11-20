import time
from datetime import datetime

import pytest
from gen3.auth import Gen3Auth
from playwright.sync_api import Page, expect
from utils import logger
from utils.test_execution import screenshot


class GWASPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}"
        # Endpoints
        self.ANALYSIS_ENDPOINT = f"{self.BASE_URL}/analysis"
        self.GWAS_UI_APP_ENDPOINT = f"{self.ANALYSIS_ENDPOINT}/GWASUIApp"
        self.GWAS_RESULTS_ENDPOINT = f"{self.ANALYSIS_ENDPOINT}/GWASResults"
        self.GWAS_WORKFLOW_API_ENDPOINT = "/ga4gh/wes/v2/workflows"
        self.GWAS_WORKFLOW_STATUS_API_ENDPOINT = "/ga4gh/wes/v2/status"
        # Locators
        self.ACCEPT_PRE_LOGIN_BUTTON = "//button[normalize-space()='Accept']"
        self.LOGIN_BUTTON = "//button[contains(text(), 'Google')]"
        self.PROJECT_SELECTOR_BOX = (
            "//*[contains(@class, 'team-project-header_modal-button')]"
        )
        self.PROJECT_SEARCH_DROPDOWN = (
            "//*[contains(@aria-labelledby, 'team-select-label')]"
        )
        self.PROJECT_SUBMISSION = "//span[normalize-space()='Submit']"
        self.COHORT_TABLE = "//*[contains(@class, 'GWASUI-mainTable')]"
        self.ADD_NEW_COHORT_BUTTON = "//button[normalize-space()='Add New Cohort']"
        self.CHECKED_RADIO = '(//*[@class="ant-radio ant-radio-checked"])'
        self.SELECT_FIRST_RADIO_BUTTON = '(//input[@type="radio"])[1]'
        self.ATTRITION_TABLE_TITLE = '//span[contains(text(),"Attrition Table")]'
        self.ATTRITION_TABLE_EXPAND_ARROW = '//div[@class="ant-collapse-expand-icon"]'
        self.ACTIVE_ATTRITION_TABLE = '//div[@data-tour="attrition-table"]'
        self.NEXT_BUTTON = '//span[contains(text(),"Next")]'
        self.PREVIOUS_BUTTON = '//span[contains(text(),"Previous")]'
        self.ADD_CONTINOUOUS_PHENOTYPE = (
            '//span[contains(text(),"Add Continuous Outcome Phenotype")]'
        )
        self.ADD_DICHOTOMOUS_PHENOTYPE = (
            '//span[contains(text(),"Add Dichotomous Outcome Phenotype")]'
        )
        self.PHENOTYPE_HISTOGRAM = '//div[@class="phenotype-histogram"]'
        self.PHENOTYPE_TABLE = '//div[@class="ant-table-container"]'
        self.RENDERED_CONTINUOUS_HISTOGRAM = '//div[@role="region"]//*[name()="svg"]'
        self.RENDERED_EULER_DIAGRAM = '//div[@id="euler"]//*[name()="svg"]'
        self.SUBMIT_BUTTON = '//button[normalize-space()="Submit"]'
        self.ADD_BUTTON = '//button[normalize-space()="Add"]'
        self.ADD_CONTINOUOUS_COVARIATE = (
            '//span[contains(text(),"Add Continuous Covariate")]'
        )
        self.ADD_DICHOTOMOUS_COVARIATE = (
            '//span[contains(text(),"Add Dichotomous Covariate")]'
        )
        self.CONFIGURE_GWAS = '//div[@class="configure-gwas_container"]'
        self.ANCESTRY_DROPDOWN = '//*[contains(@class,"ant-select ant-select-single ant-select-show-arrow ant-select-show-search")]'
        self.ANCESTRY = '//div[@title="non-Hispanic Asian"]'
        self.SUBMIT_DIALOG_BOX = '//div[@role="dialog"]'
        self.ENTER_JOB_NAME_FIELD = '//input[@class="ant-input gwas-job-name"]'
        self.SEE_STATUS_BUTTON = '//button[@id="see-status"]'
        self.SUBMISSION_SUCCESS_MESSAGE = '//div[@class="dismissable-message success"]'
        self.GWAS_RESULTS_TABLE = "//tbody"
        self.DICHOTOMOUS_COVARIATE_VALUE1_FIELD = '(//div[@class="ant-select select-cohort ant-select-single ant-select-show-arrow ant-select-show-search"])[1]'
        self.DICHOTOMOUS_COVARIATE_VALUE2_FIELD = '(//div[@class="ant-select select-cohort ant-select-single ant-select-show-arrow ant-select-show-search"])[2]'
        self.DICHOTOMOUS_COVARIATE_VALUE1 = (
            '(//div[contains(@title,"test new cohort - large")])[1]'
        )
        self.DICHOTOMOUS_COVARIATE_VALUE2 = (
            '(//div[contains(@title,"test new cohort - small")])[2]'
        )
        self.GWAS_WINDOW = '//div[@class="select-container"]'
        self.PHENOTYPE_NAME_FIELD = '//input[@id="phenotype-input"]'
        self.GWAS_COHORT_SEARCH_INPUT = (
            "//*[contains(@placeholder, 'Search by cohort name')]"
        )
        self.GWAS_CONCEPT_SEARCH_INPUT = (
            "//*[contains(@placeholder, 'Search by concept name')]"
        )
        self.COHORT_NAME = "test new cohort - catch all"
        self.CONTINUOUS_CONCEPT_ID = "2100007053"  # test new cohort - catch all
        self.CONTINUOUS_COVARIATE_CONCEPT_ID1 = "2000006000"  # height-2000006000
        self.CONTINUOUS_COVARIATE_CONCEPT_ID2 = "2000006001"  # weight-2000006001
        self.GWAS_JOB_ID_MESSAGE = "//*[contains(text(),'GWAS job id')]"
        self.UNAUTHORIZED_PROJECT_USER_ACCESS_MSG = "//*[contains(text(), 'Please reach out to') and contains(., 'to gain access to the system')]"
        self.WORKFLOW_LIMIT_MSG = "//div[@data-testid='workflow-limits-message']"
        self.WORKFLOW_LIMIT_REACHED_MSG = (
            "//*[contains(text(), 'Workflow limit reached')]"
        )

    def login(
        self,
        page: Page,
        user,
    ):
        """
        Sets up Dev Cookie for main Account and logs in with Google
        Also checks if the access_token exists after login
        """
        page.context.add_cookies(
            [
                {
                    "name": "dev_login",
                    "value": pytest.users[user],
                    "url": pytest.root_url_portal,
                }
            ]
        )
        expect(page.locator(self.LOGIN_BUTTON)).to_be_visible(timeout=10000)
        page.locator(self.ACCEPT_PRE_LOGIN_BUTTON).click()
        try:
            button = page.locator(self.LOGIN_BUTTON)
            if button.is_enabled(timeout=5000):
                button.click()
                logger.info(f"Clicked on login button : {self.LOGIN_BUTTON}")
        except Exception:
            logger.info(f"Login Button {self.LOGIN_BUTTON} not found or not enabled")
        screenshot(page, "AfterClickingLoginButton")
        expect(
            page.locator(f'//div[contains(text(), "{pytest.users[user]}")]')
        ).to_be_visible(timeout=10000)
        screenshot(page, "AfterLogin")
        access_token_cookie = next(
            (
                cookie
                for cookie in page.context.cookies()
                if cookie["name"] == "access_token"
            ),
            None,
        )
        assert (
            access_token_cookie is not None
        ), "Access token cookie not found after login"

    def goto_analysis_page(self, page: Page):
        page.goto(self.ANALYSIS_ENDPOINT)
        screenshot(page, "GWASAnalysisPage")

    def goto_gwas_ui_app_page(self, page: Page):
        page.goto(self.GWAS_UI_APP_ENDPOINT)
        screenshot(page, "GWASUIAppPage")

    def select_team_project(self, page: Page, project_name):
        project_selector_box = page.locator(self.PROJECT_SELECTOR_BOX)
        expect(project_selector_box).to_be_visible(timeout=15000)
        project_search_dropdown = page.locator(self.PROJECT_SEARCH_DROPDOWN)
        if project_search_dropdown.is_visible():
            logger.info("Project selector window is already present")
            self.select_project(page, project_name)
            return
        logger.info("Clicking on Project selector box")
        project_selector_box.click()
        logger.info("Clicking on Project selector dropdown")
        self.select_project(page, project_name)

    def select_project(self, page, project_name):
        logger.info("Clicking on the project")
        page.select_option("select#team-select", value=f"/gwas_projects/{project_name}")
        page.locator(self.PROJECT_SUBMISSION).click()
        screenshot(page, "AfterSelectingProject")

    def unauthorized_user_select_team_project(self, page: Page):
        logger.info("Verifying Msg box for unauthorized project access is displayed")
        project_selector_box = page.locator(self.UNAUTHORIZED_PROJECT_USER_ACCESS_MSG)
        expect(project_selector_box).to_be_visible(timeout=5000)
        screenshot(page, "UnauthorizedProjectUserAccessMsg")

    def select_cohort(self, page: Page):
        logger.info("Selecting Cohort from Cohort table")
        cohort_table = page.locator(self.COHORT_TABLE)
        expect(cohort_table).to_be_visible(timeout=5000)
        add_new_cohort_button = page.locator(self.ADD_NEW_COHORT_BUTTON)
        expect(add_new_cohort_button).to_be_visible(timeout=5000)
        gwas_cohort_search_input = page.locator(self.GWAS_COHORT_SEARCH_INPUT)
        gwas_cohort_search_input.fill(self.COHORT_NAME)
        select_first_radio_button = page.locator(self.SELECT_FIRST_RADIO_BUTTON)
        select_first_radio_button.click()
        screenshot(page, "CohortSelection")

    def attrition_table(self, page: Page):
        logger.info("Clicking on Attrition Table")
        attrition_table_title = page.locator(self.ATTRITION_TABLE_TITLE)
        expect(attrition_table_title).to_be_visible(timeout=5000)
        attrition_table_expand_arrow = page.locator(self.ATTRITION_TABLE_EXPAND_ARROW)
        attrition_table_expand_arrow.click()
        active_attrition_table = page.locator(self.ACTIVE_ATTRITION_TABLE)
        expect(active_attrition_table).to_be_visible(timeout=5000)

    def click_next_button(self, page: Page):
        logger.info("Clicking on Next Button")
        next_button = page.locator(self.NEXT_BUTTON)
        expect(next_button).to_be_visible(timeout=5000)
        next_button.click()

    def click_previous_button(self, page: Page):
        logger.info("Clicking on Previous Button")
        previous_button = page.locator(self.PREVIOUS_BUTTON)
        expect(previous_button).to_be_visible(timeout=5000)
        previous_button.click()

    def select_continuous_phenotype(self, page: Page):
        logger.info("Selecting Continuous Phenotype")
        add_coninuous_phenotype = page.locator(self.ADD_CONTINOUOUS_PHENOTYPE)
        expect(add_coninuous_phenotype).to_be_visible(timeout=5000)
        add_coninuous_phenotype.click()

    def select_dichotomous_phenotype(self, page: Page):
        logger.info("Selecting Dichotomous Phenotype")
        add_dichotomous_phenotype = page.locator(self.ADD_DICHOTOMOUS_PHENOTYPE)
        expect(add_dichotomous_phenotype).to_be_visible(timeout=5000)
        add_dichotomous_phenotype.click()

    def select_continuous_phenotype_concept(self, page: Page):
        phenotype_histogram = page.locator(self.PHENOTYPE_HISTOGRAM)
        expect(phenotype_histogram).to_be_visible(timeout=5000)
        phenotype_table = page.locator(self.PHENOTYPE_TABLE)
        expect(phenotype_table).to_be_visible(timeout=5000)
        gwas_concept_search_input = page.locator(self.GWAS_CONCEPT_SEARCH_INPUT)
        gwas_concept_search_input.fill(self.CONTINUOUS_CONCEPT_ID)
        select_first_radio_button = page.locator(self.SELECT_FIRST_RADIO_BUTTON)
        select_first_radio_button.click()
        rendered_continuous_histogram = page.locator(self.RENDERED_CONTINUOUS_HISTOGRAM)
        expect(rendered_continuous_histogram).to_be_visible(timeout=5000)
        screenshot(page, "ContinuousPhenotypeConcept")

    def select_dichotomous_phenotype_concept(self, page: Page):
        self.select_first_value(page)
        self.select_second_value(page)
        self.enter_phenotype_name(page)
        self.click_submit_button(page)
        screenshot(page, "DichotomousPhenotypeConcept")

    def click_submit_button(self, page: Page):
        logger.info("Clicking on Submit-Button")
        submit_button = page.locator(self.SUBMIT_BUTTON)
        expect(submit_button).to_be_visible(timeout=5000)
        submit_button.click()

    def select_continuous_covariate(self, page: Page):
        logger.info("Selecting Continuous Covariate")
        add_coninuous_covariate = page.locator(self.ADD_CONTINOUOUS_COVARIATE)
        expect(add_coninuous_covariate).to_be_visible(timeout=5000)
        add_coninuous_covariate.click()

    def select_dichotomous_covariate(self, page: Page):
        logger.info("Selecting Dichotomous Covariate")
        add_dichotomous_covariate = page.locator(self.ADD_DICHOTOMOUS_COVARIATE)
        expect(add_dichotomous_covariate).to_be_visible(timeout=5000)
        add_dichotomous_covariate.click()

    def select_first_concept(self, page: Page):
        logger.info("Selecting First Concept")
        phenotype_histogram = page.locator(self.PHENOTYPE_HISTOGRAM)
        expect(phenotype_histogram).to_be_visible(timeout=5000)
        phenotype_table = page.locator(self.PHENOTYPE_TABLE)
        expect(phenotype_table).to_be_visible(timeout=5000)
        gwas_concept_search_input = page.locator(self.GWAS_CONCEPT_SEARCH_INPUT)
        gwas_concept_search_input.fill(self.CONTINUOUS_COVARIATE_CONCEPT_ID1)
        select_first_radio_button = page.locator(self.SELECT_FIRST_RADIO_BUTTON)
        select_first_radio_button.click()
        rendered_continuous_histogram = page.locator(self.RENDERED_CONTINUOUS_HISTOGRAM)
        expect(rendered_continuous_histogram).to_be_visible(timeout=5000)
        screenshot(page, "ContinuousPhenotypeFirstConcept")

    def select_second_concept(self, page: Page):
        logger.info("Selecting Second Concept")
        phenotype_histogram = page.locator(self.PHENOTYPE_HISTOGRAM)
        expect(phenotype_histogram).to_be_visible(timeout=5000)
        phenotype_table = page.locator(self.PHENOTYPE_TABLE)
        expect(phenotype_table).to_be_visible(timeout=5000)
        gwas_concept_search_input = page.locator(self.GWAS_CONCEPT_SEARCH_INPUT)
        gwas_concept_search_input.fill(self.CONTINUOUS_COVARIATE_CONCEPT_ID2)
        select_first_radio_button = page.locator(self.SELECT_FIRST_RADIO_BUTTON)
        select_first_radio_button.click()
        rendered_continuous_histogram = page.locator(self.RENDERED_CONTINUOUS_HISTOGRAM)
        expect(rendered_continuous_histogram).to_be_visible(timeout=5000)
        screenshot(page, "ContinuousPhenotypeSecondConcept")

    def select_first_value(self, page: Page):
        logger.info("Selecting First Value")
        dichotomous_covariate_value1_field = page.locator(
            self.DICHOTOMOUS_COVARIATE_VALUE1_FIELD
        )
        expect(dichotomous_covariate_value1_field).to_be_visible(timeout=5000)
        dichotomous_covariate_value1_field.click()
        dichotomous_covariate_value1 = page.locator(self.DICHOTOMOUS_COVARIATE_VALUE1)
        expect(dichotomous_covariate_value1).to_be_visible(timeout=5000)
        dichotomous_covariate_value1.click()
        gwas_window = page.locator(self.GWAS_WINDOW)
        expect(gwas_window).to_be_visible(timeout=5000)
        gwas_window.click()

    def select_second_value(self, page: Page):
        logger.info("Selecting SECOND Value")
        dichotomous_covariate_value2_field = page.locator(
            self.DICHOTOMOUS_COVARIATE_VALUE2_FIELD
        )
        expect(dichotomous_covariate_value2_field).to_be_visible(timeout=5000)
        dichotomous_covariate_value2_field.click()
        dichotomous_covariate_value2 = page.locator(self.DICHOTOMOUS_COVARIATE_VALUE2)
        expect(dichotomous_covariate_value2).to_be_visible(timeout=5000)
        dichotomous_covariate_value2.click()
        gwas_window = page.locator(self.GWAS_WINDOW)
        expect(gwas_window).to_be_visible(timeout=5000)
        gwas_window.click()

    def enter_phenotype_name(self, page: Page):
        logger.info("Entering Phenotype Name")
        timestamp = datetime.now()
        timestamp_string = timestamp.strftime("%Y%m%d-%H%M%S")
        phenotype_name = f"Testing_{timestamp_string}"
        rendered_euler_diagram = page.locator(self.RENDERED_EULER_DIAGRAM)
        expect(rendered_euler_diagram).to_be_visible(timeout=5000)
        phenotype_name_field = page.locator(self.PHENOTYPE_NAME_FIELD)
        expect(phenotype_name_field).to_be_visible(timeout=5000)
        phenotype_name_field.fill(phenotype_name)

    def click_add_button(self, page: Page):
        logger.info("Clicking on Add Button")
        add_button = page.locator(self.ADD_BUTTON)
        expect(add_button).to_be_visible(timeout=5000)
        add_button.click()

    def select_ancestry(self, page: Page):
        logger.info("Selecting Ancestry")
        configure_gwas = page.locator(self.CONFIGURE_GWAS)
        expect(configure_gwas).to_be_visible(timeout=5000)
        ancestry_dropdown = page.locator(self.ANCESTRY_DROPDOWN)
        ancestry_dropdown.click()
        ancestry_title = page.locator(self.ANCESTRY)
        expect(ancestry_title).to_be_visible(timeout=5000)
        ancestry_title.click()

    def submit_workflow(self, page: Page):
        logger.info("Submitting Job Name")
        timestamp = datetime.now()
        timestamp_string = timestamp.strftime("%Y%m%d-%H%M%S")
        job_name = f"AutomationTest_{timestamp_string}"
        submit_dialog_box = page.locator(self.SUBMIT_DIALOG_BOX)
        expect(submit_dialog_box).to_be_visible(timeout=5000)
        enter_job_name_field = page.locator(self.ENTER_JOB_NAME_FIELD)
        enter_job_name_field.fill(job_name)
        screenshot(page, "SubmissionDialogBox")
        logger.info(f"Job Name : {job_name}")
        self.click_submit_button(page)
        job_id_message_element = page.locator(self.GWAS_JOB_ID_MESSAGE)
        expect(job_id_message_element).to_be_visible(timeout=15000)
        job_id = job_id_message_element.text_content().split()[-1].replace('"', "")
        return job_name, job_id

    def submit_workflow_after_monthly_limit_reached(self, page: Page):
        logger.info("Submitting Job Name")
        timestamp = datetime.now()
        timestamp_string = timestamp.strftime("%Y%m%d-%H%M%S")
        job_name = f"AutomationTest_{timestamp_string}"
        submit_dialog_box = page.locator(self.SUBMIT_DIALOG_BOX)
        expect(submit_dialog_box).to_be_visible(timeout=5000)
        enter_job_name_field = page.locator(self.ENTER_JOB_NAME_FIELD)
        enter_job_name_field.fill(job_name)
        screenshot(page, "SubmissionDialogBox")
        logger.info(f"Job Name : {job_name}")
        workflow_limit_reached_msg = page.locator(self.WORKFLOW_LIMIT_REACHED_MSG)
        expect(workflow_limit_reached_msg).to_be_visible(timeout=5000)
        submit_button = page.locator(self.SUBMIT_BUTTON)
        expect(submit_button).to_be_visible(timeout=5000)
        expect(submit_button).to_be_disabled()

    def verify_job_submission(self, page: Page):
        submission_success_message = page.locator(self.SUBMISSION_SUCCESS_MESSAGE)
        expect(submission_success_message).to_be_visible(timeout=10000)
        workflow_submitted, workflow_limit = self.get_workflow_limits(page)
        see_status_button = page.locator(self.SEE_STATUS_BUTTON)
        expect(see_status_button).to_be_visible(timeout=5000)
        see_status_button.click()
        gwas_results_table = page.locator(self.GWAS_RESULTS_TABLE)
        expect(gwas_results_table).to_be_visible(timeout=15000)
        current_url = page.url
        assert "GWASResults" in current_url
        self.validate_workflow_limits_with_results_page(
            page, workflow_submitted, workflow_limit
        )
        screenshot(page, "ResultsPage")

    def goto_result_page(self, page: Page):
        page.goto(self.GWAS_RESULTS_ENDPOINT)
        gwas_results_table = page.locator(self.GWAS_RESULTS_TABLE)
        expect(gwas_results_table).to_be_visible(timeout=5000)
        screenshot(page, "GWASResultsPage")

    def get_workflow_limits(self, page: Page):
        workflow_limit_msg = page.locator(self.WORKFLOW_LIMIT_MSG)
        expect(workflow_limit_msg).to_be_visible(timeout=5000)
        workflow_submitted = int(workflow_limit_msg.text_content().split()[0])
        workflow_limit = int(workflow_limit_msg.text_content().split()[-2])
        return workflow_submitted, workflow_limit

    def validate_workflow_limits_after_workflow_submission(
        self, page: Page, previous_workflow_submitted, previous_workflow_limit
    ):
        current_workflow_submitted, current_workflow_limit = self.get_workflow_limits(
            page
        )
        logger.info(f"Previous Workflow Submitted: {previous_workflow_submitted}")
        logger.info(f"Current Workflow Submitted: {current_workflow_submitted}")
        assert (
            current_workflow_submitted == previous_workflow_submitted + 1
        ), f"Workflow count is not incremented. Current limit: {current_workflow_submitted} and previous limit: {previous_workflow_submitted}"
        assert (
            current_workflow_limit == previous_workflow_limit
        ), f"Workflow count doesnot match. Current limit: {current_workflow_limit} and previous limit: {previous_workflow_limit}"

    def validate_workflow_limits_with_results_page(
        self, page: Page, workflow_submitted, workflow_limit
    ):
        results_page_workflow_submitted, results_page_workflow_limit = (
            self.get_workflow_limits(page)
        )
        logger.info(
            f"Results Page Workflow Submitted: {results_page_workflow_submitted}"
        )
        assert (
            results_page_workflow_submitted == workflow_submitted
        ), f"Workflow count doesnot match. Results page: {results_page_workflow_submitted} and current: {workflow_submitted}"
        assert (
            results_page_workflow_limit == workflow_limit
        ), f"Workflow count doesnot match. Results page limit: {results_page_workflow_limit} and current limit: {workflow_limit}"

    def get_all_workflows(self, project, user="main_account"):
        logger.info(f"Getting all worflows for project: {project}")
        url = (
            f"{self.GWAS_WORKFLOW_API_ENDPOINT}?team_projects=/gwas_projects/{project}"
        )
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = auth.curl(path=url)
        return response.json()

    def check_job_result(self, uid_value, job_id, user="main_account"):
        logger.info(f"Checking result for job: {job_id}")
        counter = 0
        url = f"{self.GWAS_WORKFLOW_STATUS_API_ENDPOINT}/{job_id}?uid={uid_value}"
        while counter < 20:
            time.sleep(30)
            auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
            response = auth.curl(path=url)
            wf_status = response.json()["phase"]
            if wf_status == "Succeeded":
                logger.info(f"Workflow Passed. Last status: {wf_status}")
                return True
            elif wf_status in ["Failed", "Error"]:
                logger.error(f"Workflow failed. Last status: {wf_status}")
                return False
        logger.error(
            f"Waited for 10mins but the Worflow neither Passed or Failed. Last status: {wf_status}"
        )
        return False
