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

all_servers = {
    'addresses_resolvable': [],
    'process_sockets': [],
    'services': [],
    'services_stopped': [],
}

db_servers = {
    'files': [],
    'mysql_databases': [],
    'mysql_users': [],
    'process_sockets': [],
    'services': [],
}

dns_servers = {
    'process_sockets': [],
    'services': [],
}

prometheus_servers = {
    'file_patterns_missing': [],
    'html_patterns': [],
    'process_sockets': [],
    'services': [],
}

web_servers = {
    'file_patterns_missing': [],
    'files': [],
    'html_patterns': [],
    'process_sockets': [],
    'services': [],
}

lab = int(os.environ.get('LAB', 6))

if lab == 2:
    web_servers['files'].append('/usr/bin/nginx:::')
    web_servers['html_patterns'].append('Welcome to nginx!')  # 2.4

if lab >= 2:
    repo['files'].append('roles/nginx/tasks/main.yaml')  # 2.4

if lab == 3:
    repo['files'] += [
        'roles/nginx/files/default',  # 3.5
        'roles/uwsgi/files/agama.ini',  # 3.3
    ]

    web_servers['files'].append('/etc/uwsgi/apps-enabled/agama.ini:::')  # 3.3

if lab >= 3:
    repo['files'].append('roles/agama/tasks/main.yaml')  # 3.2

    web_servers['files'] += [
        '/etc/nginx/sites-enabled/default:root:root:644',  # 3.5
        '/opt/agama/agama.py:::',  # 3.2
    ]
    web_servers['html_patterns'].append('v0.3 running on')  # 3.5
    web_servers['process_sockets'].append('uwsgi@tcp://127.0.0.1:5000')  # 3.3
    web_servers['services'].append('uwsgi')  # 3.4

if 13 >= lab >= 2:
    web_servers['process_sockets'].append('nginx@tcp://0.0.0.0:80')  # 2.4
    web_servers['services'].append('nginx')  # 2.4

if lab >= 4:
    repo['files'] += [
        'group_vars/all.yaml',  # 4.5
        'roles/mysql/tasks/main.yaml',  # 4.3
    ]

    db_servers['files'].append('/etc/mysql/mysql.conf.d/override.cnf:::')  # 4.4
    db_servers['mysql_databases'].append('agama')  # 4.6
    db_servers['mysql_users'].append('agama@%')  # 4.7
    db_servers['process_sockets'].append('mysqld@tcp://0.0.0.0:3306')  # 4.4
    db_servers['services'].append('mysql')  # 4.3

if 11 >= lab >= 4:
    web_servers['files'].append('/etc/uwsgi/apps-enabled/agama.ini:agama::400')  # 4.9

if lab >= 5:
    repo['files'].append('roles/bind/tasks/main.yaml')  # 5.2

    all_servers['addresses_resolvable'] += ['__my_vms__', 'taltech.ee']  # 5.6
    all_servers['services_stopped'].append('systemd-resolved')  # 5.6

    dns_servers['process_sockets'].append('named@tcp://__ip__:53')  # 5.2
    dns_servers['services'].append('bind9')  # 5.2

    web_servers['file_patterns_missing'].append('/etc/uwsgi/apps-enabled/agama.ini:192.168.4')  # 5.7

if lab >= 6:
    repo['files'] += [
      'docs/prom_queries.txt',  # 6.5
      'roles/prometheus/tasks/main.yaml',  # 6.2
    ]

    all_servers['process_sockets'].append('prometheus-node-exporter@tcp://0.0.0.0:9100')  # 6.1
    all_servers['services'].append('prometheus-node-exporter')  # 6.1

    prometheus_servers['file_patterns_missing'].append('/etc/prometheus/prometheus.yml:192.168.4')  # 6.2
    prometheus_servers['file_patterns_missing'].append('/etc/default/prometheus:127.0.0')  # 6.2
    prometheus_servers['html_patterns'] += [
      'prometheus_ready 1',  # 6.3, 6.4
      'prometheus_target_scrape_pool_targets{scrape_job="node"} 2',  # 6.2, 6.4
    ]
    prometheus_servers['process_sockets'].append('prometheus@tcp://127.0.0.1:9090')  # 6.2
    prometheus_servers['services'].append('prometheus')  # 6.2


#
# Helper functions
#

def assert_file_does_not_contain(host, file_pattern):
    file, pattern = file_pattern.split(':')
    f = testinfra.get_host(f'ansible://{host}').file(file)
    assert not f.contains(pattern), f'{f} contains {pattern}'


def assert_file_exists(host, file_owner_group_mode):
    file, owner, group, mode = file_owner_group_mode.split(':')
    f = testinfra.get_host(f'ansible://{host}').file(file)
    assert f.exists, f'{file} is missing on {host}'
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
# Any server tests
#

if lab >= 6:
    @pytest.mark.parametrize('host', get_hosts('all'))
    @pytest.mark.parametrize('service', sorted(set(all_servers['services'])))
    def test_service_is_running_and_enabled(host, service):
        assert_service_is_running_and_enabled(host, service)

    @pytest.mark.parametrize('host', get_hosts('all'))
    @pytest.mark.parametrize('process_socket', sorted(set(all_servers['process_sockets'])))
    def test_service_is_listening(host, process_socket):
        assert_process_is_listening(host, process_socket)

if lab >= 5:
    @pytest.mark.parametrize('host', get_hosts('all'))
    @pytest.mark.parametrize('service', sorted(set(all_servers['services_stopped'])))
    def test_service_is_stopped_and_disabled(host, service):
        s = testinfra.get_host(f'ansible://{host}').service(service)
        assert not s.is_running, f'{service} is still running on {host}'
        assert not s.is_enabled, f'{service} is still enabled on {host}'

    @pytest.mark.parametrize('host', get_hosts('all'))
    @pytest.mark.parametrize('addr', sorted(set(all_servers['addresses_resolvable'])))
    def test_host_is_resolvable(host, addr):
        h = testinfra.get_host(f'ansible://{host}')
        if addr == '__my_vms__':
            addrs = set(get_hosts('all'))
        else:
            addrs = [addr]

        for a in addrs:
            assert h.addr(a).is_resolvable, f'Cannot resolve {a} from {host}'


#
# DNS server tests
#

if lab >= 5:
    @pytest.mark.parametrize('host', get_hosts('dns_servers'))
    @pytest.mark.parametrize('service', sorted(set(dns_servers['services'])))
    def test_dns_service_is_running_and_enabled(host, service):
        assert_service_is_running_and_enabled(host, service)

    @pytest.mark.parametrize('host', get_hosts('dns_servers'))
    @pytest.mark.parametrize('process_socket', sorted(set(dns_servers['process_sockets'])))
    def test_dns_service_is_listening(host, process_socket):
        assert_process_is_listening(host, process_socket)


#
# Prometheus server tests
#

if lab >= 6:
    @pytest.mark.parametrize('host', get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('file_pattern', sorted(set(prometheus_servers['file_patterns_missing'])))
    def test_prometheus_server_file_does_not_contain(host, file_pattern):
        assert_file_does_not_contain(host, file_pattern)

    @pytest.mark.parametrize('host', get_hosts('prometheus') + get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('service', sorted(set(prometheus_servers['services'])))
    def test_prometheus_is_running_and_enabled(host, service):
        assert_service_is_running_and_enabled(host, service)

    @pytest.mark.parametrize('host', get_hosts('prometheus') + get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('process_socket', sorted(set(prometheus_servers['process_sockets'])))
    def test_prometheus_is_listening(host, process_socket):
        assert_process_is_listening(host, process_socket)

    @pytest.mark.parametrize('host', get_hosts('prometheus') + get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('content', sorted(set(prometheus_servers['html_patterns'])))
    def test_prometheus_html_content(host, content):
        assert_web_page_has_content(host, 'http://localhost/prometheus/metrics', content)


#
# Database server tests
#

if lab >= 4:
    @pytest.mark.parametrize('host', get_hosts('db_servers'))
    @pytest.mark.parametrize('file_owner_group_mode', sorted(set(db_servers['files'])))
    def test_db_server_file_exists(host, file_owner_group_mode):
        assert_file_exists(host, file_owner_group_mode)

    @pytest.mark.parametrize('host', get_hosts('db_servers'))
    @pytest.mark.parametrize('service', sorted(set(db_servers['services'])))
    def test_db_service_is_running_and_enabled(host, service):
        assert_service_is_running_and_enabled(host, service)

    @pytest.mark.parametrize('host', get_hosts('db_servers'))
    @pytest.mark.parametrize('process_socket', sorted(set(db_servers['process_sockets'])))
    def test_db_service_is_listening(host, process_socket):
        assert_process_is_listening(host, process_socket)

    @pytest.mark.parametrize('host', get_hosts('db_servers'))
    @pytest.mark.parametrize('database', sorted(set(db_servers['mysql_databases'])))
    def test_mysql_database_exists(host, database):
        cmd = "sudo mysql -Nse 'SHOW DATABASES'"
        r = testinfra.get_host(f'ansible://{host}').run(cmd)
        assert database in r.stdout, f'MySQL database {database} is missing on {host}'

    @pytest.mark.parametrize('host', get_hosts('db_servers'))
    @pytest.mark.parametrize('user', sorted(set(db_servers['mysql_users'])))
    def test_mysql_user_exists(host, user):
        h = testinfra.get_host(f'ansible://{host}')

        r = h.run("sudo mysql -Nse 'SELECT CONCAT(User, \"@\", Host) FROM mysql.user'")
        assert user in r.stdout, f'MySQL user {user} is missing on {host}'

        expected_user_grants = {
            'agama@%': 'ALL PRIVILEGES ON `agama`.*',  # 4.7
        }

        r = h.run("sudo mysql -Nse 'SHOW GRANTS FOR %s'" % user.replace('%', '`%`'))
        grant_str = r.stdout.splitlines()[-1].split(' TO ')[0].replace('GRANT ', '')
        assert grant_str == expected_user_grants[user], ' '.join([
            f'MySQL user grants are wrong: {grant_str},',
            f"expected: {expected_user_grants[user]}",
        ])


#
# Web server tests (labs 2+)
#

if lab >= 2:
    @pytest.mark.parametrize('host', get_hosts('web_servers'))
    @pytest.mark.parametrize('file_owner_group_mode', sorted(set(web_servers['files'])))
    def test_web_server_file_exists(host, file_owner_group_mode):
        assert_file_exists(host, file_owner_group_mode)

    @pytest.mark.parametrize('host', get_hosts('web_servers'))
    @pytest.mark.parametrize('service', sorted(set(web_servers['services'])))
    def test_web_service_is_running_and_enabled(host, service):
        assert_service_is_running_and_enabled(host, service)

    @pytest.mark.parametrize('host', get_hosts('web_servers'))
    @pytest.mark.parametrize('process_socket', sorted(set(web_servers['process_sockets'])))
    def test_web_service_is_listening(host, process_socket):
        assert_process_is_listening(host, process_socket)

    @pytest.mark.parametrize('host', get_hosts('web_servers'))
    @pytest.mark.parametrize('content', sorted(set(web_servers['html_patterns'])))
    def test_web_server_html_content(host, content):
        assert_web_page_has_content(host, 'http://localhost', content)

if lab >= 5:
    @pytest.mark.parametrize('host', get_hosts('web_servers'))
    @pytest.mark.parametrize('file_pattern', sorted(set(web_servers['file_patterns_missing'])))
    def test_web_server_file_does_not_contain(host, file_pattern):
        assert_file_does_not_contain(host, file_pattern)


#
# Main
#

atexit.register(cleanup)
