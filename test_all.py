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
    'file_patterns_missing': [],
    'process_sockets': [],
    'services': [],
    'services_stopped': [],
    'users': [],
}

db_servers = {
    'files': [],
    'mysql_metrics': [],
    'mysql_databases': [],
    'mysql_users': [],
    'mysql_users_forbidden': [],
    'process_sockets': [],
    'services': [],
}

dns_servers = {
    'bind_metrics': [],
    'process_sockets': [],
    'services': [],
}

grafana_servers = {
    'files': [],
    'html_patterns': [],
    'process_sockets': [],
    'services': [],
}

prometheus_servers = {
    'file_patterns_missing': [],
    'nginx_metrics': [],
    'prometheus_metrics': [],
    'process_sockets': [],
    'services': [],
}

web_servers = {
    'file_patterns_missing': [],
    'files': [],
    'html_patterns': [],
    'nginx_metrics': [],
    'process_sockets': [],
    'services': [],
}

lab = int(os.environ.get('LAB', 8))

if lab == 2:
    web_servers['files'].append('/usr/bin/nginx:::')
    web_servers['html_patterns'].append('Welcome to nginx!')  # 2.4

if lab >= 2:
    repo['files'].append('roles/nginx/tasks/main.yaml')  # 2.4

if 13 >= lab >= 2:
    web_servers['process_sockets'].append('nginx@tcp://0.0.0.0:80')  # 2.4
    web_servers['services'].append('nginx')  # 2.4

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

if 11 >= lab >= 3:
    repo['files'].append('roles/uwsgi/tasks/main.yaml')  # 3.3

    web_servers['process_sockets'].append('uwsgi@tcp://127.0.0.1:5000')  # 3.3
    web_servers['services'].append('uwsgi')  # 3.4

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

    prometheus_servers['file_patterns_missing'] += [
        '/etc/default/prometheus:127.0.0',  # 6.2
        '/etc/prometheus/prometheus.yml:192.168.4',  # 6.2
    ]
    prometheus_servers['prometheus_metrics'] += [
        'prometheus_ready 1',  # 6.3, 6.4
        'prometheus_target_scrape_pool_targets{scrape_job="node"} 2',  # 6.2, 6.4
    ]
    prometheus_servers['process_sockets'] += [
        'nginx@tcp://0.0.0.0:80',  # 6.3
        'prometheus@tcp://127.0.0.1:9090',  # 6.2
    ]
    prometheus_servers['services'] += [
        'nginx',  # 6.3
        'prometheus',  # 6.2
    ]

if lab >= 7:
    repo['files'] += [
        'roles/grafana/files/main.json',  # 7.7
        'roles/grafana/tasks/main.yaml',  # 7.4
    ]

    db_servers['files'].append('/var/lib/prometheus/.my.cnf:prometheus::400')  # 7.1
    db_servers['mysql_metrics'].append('mysql_up 1')  # 7.1
    db_servers['mysql_users'].append('exporter@localhost')  # 7.1
    db_servers['mysql_users_forbidden'].append('exporter@%')  # 7.1
    db_servers['process_sockets'].append('prometheus-mysqld-exporter@tcp://0.0.0.0:9104')  # 7.1
    db_servers['services'].append('prometheus-mysqld-exporter')  # 7.1

    dns_servers['bind_metrics'].append('bind_up 1')  # 7.2
    dns_servers['process_sockets'] += [
        'named@tcp://127.0.0.1:8053',  # 7.2
        'prometheus-bind-exporter@tcp://0.0.0.0:9119',  # 7.2
    ]
    dns_servers['services'].append('prometheus-bind-exporter')  # 7.2

    grafana_servers['html_patterns'].append('<title>Grafana')  # 7.5

    prometheus_servers['nginx_metrics'].append('nginx_up 1')  # 7.3
    prometheus_servers['prometheus_metrics'] += [
        'prometheus_target_scrape_pool_targets{scrape_job="bind"} 1',  # 7.2
        'prometheus_target_scrape_pool_targets{scrape_job="mysql"} 1',  # 7.1
        'prometheus_target_scrape_pool_targets{scrape_job="nginx"} 2',  # 7.3
    ]
    prometheus_servers['process_sockets'] += [
        'nginx@tcp://127.0.0.1:8080',  # 7.3
        'prometheus-nginx-exporter@tcp://0.0.0.0:9113',  # 7.3
    ]
    prometheus_servers['services'].append('prometheus-nginx-exporter')  # 7.3

if 11 >= lab >= 7:
    grafana_servers['files'].append('/etc/grafana/grafana.ini:root:grafana:640')  # 7.4
    # Need to use 127.0.0.1 in the Grafana configuration to bind to local interface
    grafana_servers['process_sockets'].append('grafana-server@tcp://0.0.0.0:3000')  # 7.4
    grafana_servers['services'].append('grafana-server')  # 7.4

if 13 >= lab >= 7:
    web_servers['nginx_metrics'].append('nginx_up 1')  # 7.3
    web_servers['process_sockets'] += [
        'nginx@tcp://127.0.0.1:8080',  # 7.3
        'prometheus-nginx-exporter@tcp://0.0.0.0:9113',  # 7.3
    ]
    web_servers['services'].append('prometheus-nginx-exporter')  # 7.3

if lab >= 8:
    repo['files'] += [
        'roles/loki/tasks/main.yaml',  # 8.1
    ]

    all_servers['file_patterns_missing'].append('/etc/promtail/config.yml:192.168.4')  # 8.2 (implicit)
    all_servers['users'].append('promtail:adm')  # 8.2

    prometheus_servers['prometheus_metrics'] += [
        'prometheus_target_scrape_pool_targets{scrape_job="loki"} 1',  # 8.4
        'prometheus_target_scrape_pool_targets{scrape_job="promtail"} 2',  # 8.4
    ]

if 11 >= lab >= 8:
    web_servers['files'].append('/var/log/uwsgi/app/agama.log:root:adm:640')  # 8.3


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
    if '127.0.0.1' in socket:
        # If checking for local interface, also ensure the process is not listening on the public one
        socket = socket.replace('127.0.0.1', '0.0.0.0')
        assert not h.socket(socket).is_listening, f'{process} is still listening on {host} socket {socket}'


def assert_service_is_running_and_enabled(host, service):
    s = testinfra.get_host(f'ansible://{host}').service(service)
    assert s.exists, f'{service} is not installed on {host}'
    assert s.is_running, f'{service} is not running on {host}'
    assert s.is_enabled, f'{service} is not enabled on {host}'


def assert_user_exists(host, user_groups):
    user, groups_cs = user_groups.split(':')
    groups = groups_cs.split(',') if groups_cs else []
    u = testinfra.get_host(f'ansible://{host}').user(user)
    assert u.exists, f'User {user} does not exist on {host}'
    if groups:
        for group in groups:
            assert group in u.groups, f'User {user} is not a member of group {group} on {host}'


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

if lab >= 8:
    @pytest.mark.parametrize('host', get_hosts('all'))
    def test_promtail_is_running_and_enabled(host):
        assert_service_is_running_and_enabled(host, 'promtail')  # 8.2

    @pytest.mark.parametrize('host', get_hosts('all'))
    def test_promtail_is_listening(host):
        assert_process_is_listening(host, 'promtail@tcp://0.0.0.0:9080')  # 8.2

    @pytest.mark.parametrize('host', get_hosts('all'))
    @pytest.mark.parametrize('user_groups', sorted(set(all_servers['users'])))
    def test_user_exists(host, user_groups):
        assert_user_exists(host, user_groups)

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

if lab >= 7:
    @pytest.mark.parametrize('host', get_hosts('dns_servers'))
    @pytest.mark.parametrize('metric', sorted(set(dns_servers['bind_metrics'])))
    def test_bind_metric_exposed(host, metric):
        assert_web_page_has_content(host, 'http://localhost:9119/metrics', metric)


#
# Prometheus server tests
#

if lab >= 6:
    @pytest.mark.parametrize('host', get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('file_pattern', sorted(set(prometheus_servers['file_patterns_missing'])))
    def test_prometheus_server_file_does_not_contain(host, file_pattern):
        assert_file_does_not_contain(host, file_pattern)

    @pytest.mark.parametrize('host', get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('service', sorted(set(prometheus_servers['services'])))
    def test_prometheus_sevice_is_running_and_enabled(host, service):
        assert_service_is_running_and_enabled(host, service)

    @pytest.mark.parametrize('host', get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('process_socket', sorted(set(prometheus_servers['process_sockets'])))
    def test_prometheus_service_is_listening(host, process_socket):
        assert_process_is_listening(host, process_socket)

    @pytest.mark.parametrize('host', get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('metric', sorted(set(prometheus_servers['prometheus_metrics'])))
    def test_prometheus_metric_exposed(host, metric):
        assert_web_page_has_content(host, 'http://localhost/prometheus/metrics', metric)

if lab >= 7:
    @pytest.mark.parametrize('host', get_hosts('prometheus_servers'))
    @pytest.mark.parametrize('metric', sorted(set(prometheus_servers['nginx_metrics'])))
    def test_prometheus_server_nginx_metric_exposed(host, metric):
        assert_web_page_has_content(host, 'http://localhost:9113/metrics', metric)


#
# Loki server tests
#

if lab >= 8:
    @pytest.mark.parametrize('host', get_hosts('loki_servers'))
    def test_loki_is_running_and_enabled(host):
        assert_service_is_running_and_enabled(host, 'loki')  # 8.1

    @pytest.mark.parametrize('host', get_hosts('loki_servers'))
    def test_loki_is_listening(host):
        assert_process_is_listening(host, 'loki@tcp://0.0.0.0:3100')  # 8.1

    @pytest.mark.parametrize('host', get_hosts('loki_servers'))
    def test_loki_html_content(host):
        assert_web_page_has_content(host, 'http://localhost:3100/ready', 'ready')  # 8.1


#
# Grafana server tests
#

if lab >= 7:
    @pytest.mark.parametrize('host', get_hosts('grafana_servers'))
    @pytest.mark.parametrize('file_owner_group_mode', sorted(set(grafana_servers['files'])))
    def test_grafana_file_exists(host, file_owner_group_mode):
        assert_file_exists(host, file_owner_group_mode)

    @pytest.mark.parametrize('host', get_hosts('grafana_servers'))
    @pytest.mark.parametrize('service', sorted(set(grafana_servers['services'])))
    def test_grafana_is_running_and_enabled(host, service):
        assert_service_is_running_and_enabled(host, service)

    @pytest.mark.parametrize('host', get_hosts('grafana_servers'))
    @pytest.mark.parametrize('process_socket', sorted(set(grafana_servers['process_sockets'])))
    def test_grafana_is_listening(host, process_socket):
        assert_process_is_listening(host, process_socket)

    @pytest.mark.parametrize('host', get_hosts('grafana_servers'))
    @pytest.mark.parametrize('content', sorted(set(grafana_servers['html_patterns'])))
    def test_grafana_html_content(host, content):
        assert_web_page_has_content(host, 'http://localhost/grafana', content)


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
            'exporter@localhost': 'SELECT, PROCESS, REPLICATION CLIENT ON *.*',  # 7.1
        }

        r = h.run("sudo mysql -Nse 'SHOW GRANTS FOR %s'" % user.replace('%', '`%`'))
        grant_str = r.stdout.splitlines()[-1].split(' TO ')[0].replace('GRANT ', '')
        assert grant_str == expected_user_grants[user], ' '.join([
            f'MySQL user grants are wrong: {grant_str},',
            f"expected: {expected_user_grants[user]}",
        ])

if lab >= 7:
    @pytest.mark.parametrize('host', get_hosts('db_servers'))
    @pytest.mark.parametrize('metric', sorted(set(db_servers['mysql_metrics'])))
    def test_mysql_metric_exposed(host, metric):
        assert_web_page_has_content(host, 'http://localhost:9104/metrics', metric)


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

if lab >= 7:
    @pytest.mark.parametrize('host', get_hosts('web_servers'))
    @pytest.mark.parametrize('metric', sorted(set(web_servers['nginx_metrics'])))
    def test_web_server_nginx_metric_exposed(host, metric):
        assert_web_page_has_content(host, 'http://localhost:9113/metrics', metric)


#
# Main
#

atexit.register(cleanup)
