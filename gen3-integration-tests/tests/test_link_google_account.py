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
        Scenario:
        Steps:
            1. Linking the google account for user main_account
            2. Check the status of the linking is 200
            3. Unlink the google account for user main_account
        """
        self.fence.link_google_account(user="main_account")
        self.fence.unlink_google_account(user="main_account")

    def test_extend_expiration_before_expiration(self):
        """
        Scenario:
        Steps:
            1. Linking the google account for user main_account
            2. Extend the expiration time for the linking and check if it got applied
            3. Unlink the google account for user main_account
        """
        self.fence.link_google_account(user="main_account")
        self.fence.extend_expiration(user="main_account", expires_in=5)
        self.fence.unlink_google_account(user="main_account")

    def test_extend_expiration_after_expiration(self):
        """
        Scenario:
        Steps:
            1. Linking the google account for user main_account with expires_in parameter of 5secs
            2. Get the 'exp' form the url and validate the expiration time
            3. Wait for 5 secs so that expiration time lapses
            4. Then try to extend the expiration on the link and validate the expiration time
            5. Unlink the google account for user main_account
        """
        expires_in = 5
        request_time = datetime.datetime.now()
        # linking google account which returns redirect url with email and exp
        linking_url, status_code = self.fence.link_google_account(
            user="main_account", expires_in=expires_in
        )
        assert status_code == 200, f"Expected status code 200, got {status_code}"
        # get exp from redirect url
        match = re.search(r"exp=(\d+)", linking_url)
        link_exp_value = match.group(1) if match else None
        assert (
            link_exp_value is not None
        ), "The 'exp' value could not be found in the URL."
        # convert timestamp in datetime format and compare if it is within range
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
        self.fence.extend_expiration(user="main_account")
        self.fence.unlink_google_account(user="main_account")

    def test_unlink_unlinked_account(self):
        """
        Scenario:
        Steps:
            1. Unlink the account which does not have any linked account
            2. Expect 404 status_code
        """
        status_code = self.fence.unlink_google_account(user="auxAcct2_account")
        assert status_code == 404

    def test_extend_link_unlinked_account(self):
        """
        Scenario:
        Steps:
            1. Try to extend the expiration time of unlinked_account
            2. Expect 404 status_code
        """
        status_code = self.fence.extend_expiration(user="main_account")
        assert status_code == 404

    def test_link_already_linked_account(self):
        """
        Scenario:
        Steps:
            1. Linking the google account for user main_account
            2. Check the status of the linking is 200
            3. Again try to link the google account for user main_account and expect error message
            4. Unlink the google account for user main_account
        """
        # linking the google account for the first time
        self.fence.link_google_account(user="main_account")

        # linking the google account for the second time
        linking_url, status_code = self.fence.link_google_account(user="main_account")
        match = re.search(r"error_description=([^&]+)", linking_url)
        error_description_message = match.group(1) if match else None
        expected_error = "User+already+has+a+linked+Google+account."
        assert (
            error_description_message == expected_error
        ), f"Expected '{expected_error}', but got '{error_description_message}'"

        # unlink google account
        self.fence.unlink_google_account(user="main_account")

    def test_link_already_linked_account_with_diff_user(self):
        """
        Scenario:
        Steps:
            1. Linking the google account for user auxAcct1
            2. Run the jenkins job to force-link auxAcct1 with main_account email id
            3. Then try to link google account with user main_account with main_account email id
            4. Expect an error saying "The account specified is already linked to a different user."
            . Unlink the google account for user auxAcct1
        """
        # linking the google account to ensure a proxy group is created for the user
        self.fence.link_google_account(user="auxAcct1_account")

        # send a force-link-google command to link user dummy-one with email cdis.autotest@gmail.com
        self.fence.force_linking(
            pytest.users["auxAcct1_account"], pytest.users["main_account"]
        )

        # # try to link google account for user cdis.auto with same email cdis.autotest@gmail.com which is linked to dummy-one user
        linking_url, status_code = self.fence.link_google_account(user="main_account")
        assert status_code == 200, f"Expected status code 200, got {status_code}"
        match = re.search(r"error_description=([^&]+)", linking_url)
        error_description_message = match.group(1) if match else None
        expected_error = "Could+not+link+Google+account.+The+account+specified+is+already+linked+to+a+different+user."
        assert (
            error_description_message == expected_error
        ), f"Expected '{expected_error}', but got '{error_description_message}'"

        # unlink google account for user dummy-one
        self.fence.unlink_google_account(user="auxAcct1_account")
        self.fence.unlink_google_account(user="main_account")
