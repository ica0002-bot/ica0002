# Resources for IT Infrastructure Services Course

## Add name file

Create a file called `name.txt` in the root of your repo with this content:

	real name:github username:discord username

Example:

	Roman Kuchin:romankuchin:RomanK

Wrong:

	real name: Roman Kuchin
	github username: romankuchin

Also wrong:

	real name: Roman Kuchin username: romankuchin

This file is be used in some scripts, and also on the final lab defence (to match your code with your grade in OIS).


## Add inventory script to your repository

We are rebuilding VMs every night, so Ansible inventory file would need to be changed every new day you want to provision your infrastructure.

Luckily Ansible supports dynamic inventories -- scripts that output JSON of certain format.

You can check your inventory file at https://ica0002-bot.github.io/students/{your-github-username}/inventory.json -- it's updated every time your VMs are rebuilt.

To make Ansible use it you will need an inventory script, and configuration file change that tells Ansible where to query your inventory from.

Copy `ansible.cfg` and `inventory.sh` to your repository, make `inventory.sh` executable, commit and push to GitHub:

	curl -O https://raw.githubusercontent.com/ica0002-bot/ica0002/refs/heads/main/ansible.cfg
	curl -O https://raw.githubusercontent.com/ica0002-bot/ica0002/refs/heads/main/inventory.sh
	chmod +x inventory.sh

	git add ansible.cfg inventory.sh
	git commit -m 'Add inventory script'
	git push

Note: this will overwrite `ansible.cfg` and `inventory.sh` files in your repository if you have created them already!


## Add tests to your repository

Copy `run-tests.sh` to your repository, make it executable, commit and push to GitHub:

	curl -O https://raw.githubusercontent.com/ica0002-bot/ica0002/refs/heads/main/run-tests.sh
	chmod +x run-tests.sh

	git add run-tests.sh
	git commit -m 'Add tests'
	git push

Note: this will overwrite `run-tests.sh` file in your repository if you have created it already!

You're all set! Now you can run `./run-tests.sh` any time to test your solution.

Feel free to update the script in your repository to better match your needs. Make sure to commit and push the changes!

Test cases are available [here](https://github.com/ica0002-bot/ica0002/blob/main/test_all.py); we'll update them for (almost) every lab, and the script will download the updated version to your repository.
