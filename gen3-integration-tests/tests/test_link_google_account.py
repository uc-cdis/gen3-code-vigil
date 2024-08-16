import pytest
import re
import datetime
import time

from utils import logger
from services.fence import Fence


@pytest.mark.fence
class TestLinkGoogleAccount:
    fence = Fence()

    def test_link_unlink_google_account(self):
        """
        Scenario: Link and Unlink Google Account
        Steps:
            1. Linking the google account for user main_account
            2. Check the status of the linking is 200
            3. Unlink the google account for user main_account
        """
        # Linking the google account for user main_account
        linking_url, linking_status_code = self.fence.link_google_account(
            user="main_account"
        )
        assert (
            linking_status_code == 200
        ), f"Expected Google account to be linked, but got status_code {linking_status_code}"
        # Unlinking the google account for user main_account
        unlink_status_code = self.fence.unlink_google_account(user="main_account")
        assert (
            unlink_status_code == 200
        ), f"Expected Google account to be unlinked, but got status_code {unlink_status_code}"

    def test_extend_expiration_before_expiration(self):
        """
        Scenario: Extending expiration time on link before expiration time
        Steps:
            1. Linking the google account for user main_account
            2. Extend the expiration time for the linking and check if it got applied
            3. Unlink the google account for user main_account
        """
        # Linking the google account for user main_account
        linking_url, linking_status_code = self.fence.link_google_account(
            user="main_account"
        )
        assert (
            linking_status_code == 200
        ), f"Expected Google account to be linked, but got status_code {linking_status_code}"
        # Extend th expiration time on the google account link
        extend_status_code = self.fence.extend_expiration(
            user="main_account", expires_in=5
        )
        assert (
            extend_status_code == 200
        ), f"Expiration time on the link was not extended, got status_code {extend_status_code} "
        # Unlinking the google account for user main_account
        unlink_status_code = self.fence.unlink_google_account(user="main_account")
        assert (
            unlink_status_code == 200
        ), f"Expected Google account to be unlinked, but got status_code {unlink_status_code}"

    def test_extend_expiration_after_expiration(self):
        """
        Scenario: Extending expiration time on link after expiration time
        Steps:
            1. Linking the google account for user main_account with expires_in parameter of 5secs
            2. Get the 'exp' form the url and validate the expiration time
            3. Wait for 5 secs so that expiration time lapses
            4. Then try to extend the expiration on the link and validate the expiration time
            5. Unlink the google account for user main_account
        """
        expires_in = 5
        request_time = datetime.datetime.now()
        # Linking google account for user main_account which returns redirect url with email and exp
        linking_url, linking_status_code = self.fence.link_google_account(
            user="main_account", expires_in=expires_in
        )
        assert (
            linking_status_code == 200
        ), f"Expected status code 200, got {linking_status_code}"
        # Get exp from redirect url
        match = re.search(r"exp=(\d+)", linking_url)
        link_exp_value = match.group(1) if match else None
        assert (
            link_exp_value is not None
        ), "The 'exp' value could not be found in the URL."
        # Convert timestamp in datetime format and compare if it is within range
        expiration_value = datetime.datetime.fromtimestamp(int(link_exp_value))
        expected_expiration_value = expiration_value - request_time
        min = datetime.timedelta(seconds=expires_in - 5)
        max = datetime.timedelta(seconds=expires_in + 5)
        assert (
            min <= expected_expiration_value <= max
        ), f"The link should be set to expire in {expires_in} secs"
        # sleep/wait for expires_in so that link expiration time is lapsed before trying to extend the expiration time
        time.sleep(expires_in)
        # now try to extend the expiration time again
        extend_status_code = self.fence.extend_expiration(user="main_account")
        assert (
            extend_status_code == 200
        ), f"Expiration time on the link was not extended, got status_code {extend_status_code}"
        # Unlinking the google account for user main_account
        unlink_status_code = self.fence.unlink_google_account(user="main_account")
        assert (
            unlink_status_code == 200
        ), f"Expected Google account to be unlinked, but got status_code {unlink_status_code}"

    def test_unlink_unlinked_account(self):
        """
        Scenario: Unlinking unlinked account
        Steps:
            1. Unlink the account which does not have any linked account
            2. Expect 404 status_code
        """
        unlink_status_code = self.fence.unlink_google_account(user="auxAcct2_account")
        assert (
            unlink_status_code == 404
        ), f"Expected 404 status_code error unlinking unlinked account, got status_code {unlink_status_code}"

    def test_extend_link_unlinked_account(self):
        """
        Scenario: Extend expiration time on unlinked account
        Steps:
            1. Try to extend the expiration time of unlinked_account
            2. Expect 404 status_code
        """
        extend_status_code = self.fence.extend_expiration(user="main_account")
        assert (
            extend_status_code == 404
        ), f"Expected 404 status_code error while trying to extend expiration on unlinked account, got status_code {extend_status_code}"

    def test_link_already_linked_account(self):
        """
        Scenario: Linking already linked account
        Steps:
            1. Linking the google account for user main_account
            2. Check the status of the linking is 200
            3. Again try to link the google account for user main_account and expect error message
            4. Unlink the google account for user main_account
        """
        # Linking the google account for user main_account the first time
        logger.info("Linking google account for first time ...")
        first_linking_url, first_status_code = self.fence.link_google_account(
            user="main_account"
        )
        assert (
            first_status_code == 200
        ), f"Expected Google account to be linked, but got status_code {first_status_code}"

        # Linking the google account for the second time
        logger.info("Linking google account for second time ...")
        linking_url, status_code = self.fence.link_google_account(user="main_account")
        assert (
            status_code == 200
        ), f"Expected Google account to be linked, but got status_code {status_code}"
        match = re.search(r"error_description=([^&]+)", linking_url)
        error_description_message = match.group(1) if match else None
        expected_error = "User+already+has+a+linked+Google+account."
        assert (
            error_description_message == expected_error
        ), f"Expected '{expected_error}', but got '{error_description_message}'"

        # Unlinking the google account for user main_account
        unlink_status_code = self.fence.unlink_google_account(user="main_account")
        assert (
            unlink_status_code == 200
        ), f"Expected Google account to be unlinked, but got status_code {unlink_status_code}"

    def test_link_already_linked_account_with_diff_user(self):
        """
        Scenario: Linking account with email address linked to different account
        Steps:
            1. Linking the google account for user auxAcct1
            2. Run the jenkins job to force-link auxAcct1 with main_account email id
            3. Then try to link google account with user main_account with main_account email id
            4. Expect an error saying "The account specified is already linked to a different user."
            . Unlink the google account for user auxAcct1
        """
        # Linking the google account to ensure a proxy group is created for the user auxAcct1
        linking_url, status_code = self.fence.link_google_account(user="auxAcct1_account")
        assert (
            status_code == 200
        ), f"Expected Google account to be linked, but got status_code {status_code}"

        # send a force-link-google command to link user auxAcct1 with email cdis.autotest@gmail.com
        self.fence.force_linking(
            pytest.users["auxAcct1_account"], pytest.users["main_account"]
        )

        # try to link google account for user main_account with same email cdis.autotest@gmail.com which is linked to dummy-one user
        linking_url, status_code = self.fence.link_google_account(user="main_account")
        assert status_code == 200, f"Expected status code 200, got {status_code}"
        match = re.search(r"error_description=([^&]+)", linking_url)
        error_description_message = match.group(1) if match else None
        expected_error = "Could+not+link+Google+account.+The+account+specified+is+already+linked+to+a+different+user."
        assert (
            error_description_message == expected_error
        ), f"Expected '{expected_error}', but got '{error_description_message}'"

        # Unlinking the google account for user auxAcct1 and main_account
        unlink_status_code = self.fence.unlink_google_account(user="auxAcct1_account")
        assert (
            unlink_status_code == 200
        ), f"Expected Google account to be unlinked, but got status_code {unlink_status_code}"
        unlink_main_account_status_code = self.fence.unlink_google_account(
            user="main_account"
        )
        assert (
            unlink_main_account_status_code == 200
        ), f"Expected Google account to be unlinked, but got status_code {unlink_main_account_status_code}"
