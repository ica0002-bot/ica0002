# Resources for IT Infrastructure Services Course

## Add tests to your repository

Copy `run-tests.sh` to your repository, make it executable, commit and push to GitHub:

	wget https://raw.githubusercontent.com/ica0002-bot/ica0002/refs/heads/main/run-tests.sh
	chmod +x run-tests.sh

	git add run-tests.sh
	git commit -m 'Add tests'
	git push

You're all set! Now you can run `./run-tests.sh` any time to test your solution.

Feel free to update the script in your repository to better match your needs. Make sure to commit and push the changes!

Test cases are available [here](https://github.com/ica0002-bot/ica0002/blob/main/test_all.py); we'll update them for (almost) every lab, and the script will download the updated version to your repository.
