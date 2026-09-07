#!/usr/bin/env python3

import atexit
import json
import os
import pytest
import shutil
import subprocess
import testinfra


#
# Test entities
#

repo = {
    'files': ['ansible.cfg', 'infra.yaml', 'roles/init/tasks/main.yaml'],  # 1.6
}

web_servers = {
    'html_patterns': [],
    'process_sockets': [],
    'services': [],
}

lab = int(os.environ.get('LAB', 2))

if lab == 2:
    web_servers['html_patterns'].append('Welcome to nginx!')  # 2.4

if lab >= 2:
    repo['files'].append('roles/nginx/tasks/main.yaml')  # 2.4

if 13 >= lab >= 2:
    web_servers['process_sockets'].append('nginx@tcp://0.0.0.0:80')  # 2.4
    web_servers['services'].append('nginx')  # 2.4


#
# Helper functions
#

def assert_file_exists(host, file_owner_group_mode):
    file, owner, group, mode = file_owner_group_mode.split(':')
    f = testinfra.get_host(f'ansible://{host}').file(file)
    if owner:
        if owner.isdigit():
            assert f.uid == int(owner), f'{file} has wrong owner id: {f.uid}'
        else:
            assert f.user == owner, f'{file} has wrong owner: {f.user}'
    if group:
        assert f.group == group, f'{file} has wrong group: {f.group}'
    if mode:
        mode = int(mode, 8)
        assert f.mode == mode, f'{file} has wrong permissions; expected: {mode:o}'


def assert_process_is_listening(host, process_socket):
    process, socket = process_socket.split('@')
    h = testinfra.get_host(f'ansible://{host}')
    if '__ip__' in socket:
        ip_addr = h.interface('ens3').addresses[0]
        socket = socket.replace('__ip__', ip_addr)
    assert h.socket(socket).is_listening, f'{process} is not listening on {host} socket {socket}'


def assert_service_is_running_and_enabled(host, service):
    s = testinfra.get_host(f'ansible://{host}').service(service)
    assert s.exists, f'{service} is not installed on {host}'
    assert s.is_running, f'{service} is not running on {host}'
    assert s.is_enabled, f'{service} is not enabled on {host}'


def assert_web_page_has_content(host, url, content):
    r = testinfra.get_host(f'ansible://{host}').run(f'curl -Ls {url}')
    assert content in r.stdout, f'Required content is not found on {host} -> {url}'


def cleanup():
    shutil.rmtree('.pytest_cache', ignore_errors=True)
    shutil.rmtree('__pycache__', ignore_errors=True)


def get_hosts(group):
    out = subprocess.check_output(['ansible-inventory', '--list'])
    inventory = json.loads(out)

    if group not in inventory:
        return []

    if group == 'all':
        return inventory['_meta']['hostvars'].keys()

    if 'hosts' in inventory[group]:
        return inventory[group]['hosts']

    return []


#
# Local tests
#

def test_local_ansible_version():
    out = subprocess.check_output(['ansible', '--version'], text=True).partition('\n')[0]
    assert 'ansible [core 2.21.' in out, f'Wrong Ansible version: {out}'


@pytest.mark.parametrize('file', sorted(set(repo['files'])))
def test_local_repo_file_exists(file):
    assert os.path.exists(file), f'{file} is missing in the repository'


#
# Web server tests (labs 2+)
#

@pytest.mark.parametrize('host', get_hosts('web_servers'))
@pytest.mark.parametrize('process_socket', sorted(set(web_servers['process_sockets'])))
def test_web_service_is_listening(host, process_socket):
    assert_process_is_listening(host, process_socket)


@pytest.mark.parametrize('host', get_hosts('web_servers'))
@pytest.mark.parametrize('service', sorted(set(web_servers['services'])))
def test_web_service_is_running_and_enabled(host, service):
    assert_service_is_running_and_enabled(host, service)


@pytest.mark.parametrize('host', get_hosts('web_servers'))
@pytest.mark.parametrize('content', sorted(set(web_servers['html_patterns'])))
def test_web_server_html_content(host, content):
    assert_web_page_has_content(host, 'http://localhost', content)


#
# Main
#

atexit.register(cleanup)
