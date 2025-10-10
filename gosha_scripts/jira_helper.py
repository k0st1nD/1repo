# coding: utf-8
import re
import datetime
import simplejson as json
from copy import copy
from dateutil import parser
from math import floor, ceil
from functools import reduce
from typing import List, Dict, Tuple

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


_NONE_ACTIVE_BACKLOGS = ('К планированию', 'Актуальный бэклог', 'К грумингу', 'Дизайн бэклог',
                         'Баги клиентского Альфа-офиса', 'Баги с приоритетом')
_STATUS_IN_PROGRESS = ('in progress', 'to fix', 'На исправление')
_STATUSES_FINISHED = ('done', 'prod', 'passed', 'deployed to production', 'closed', 'fixed', 'Исправления внесены')
_STATUS_DONE = 'done'
_DEV_TASKS = ('Sub-task', 'DevTask')
_NULL = '<null>'

_STACKS = ('analyse', 'front', 'middle', 'pega', 'test')

_NEW = (
    '#TODO#',
    'new',
    'to do',
    'reopened',
    # 'аналитика',
)

_BA = (
    'бизнес анализ',
)

_PRED_PBR = (
    'согласование бизнес аналитики',
)

_SA_WAIT = (
    'бизнес аналитика подготовлена',
)

_SA = (
    'подготовка системной аналитики',
)

_PBR = (
    'к груммингу',
    'к PBR',
)

_PLANNING = (
    'к планингу',
)

_SPRINT_TODO = (
    'to develop',
)

_INPR = (
    'in progress',
)

_INPR_HOLD = (
    'in progress - hold',
)

_REVIEW = (
    'review',
)

_DEV = (
    'dev - ready to test',
    'dev - testing',
    'testing',
    'dev - testing done',
)

_DEV_READY = (
    'dev - ready to test',
)

_DEV_TESTING = (
    'dev - testing',
    'testing',
)

_DEV_WAITING = (
    'dev - testing done',
)

_DEV_HOLD = (
    'dev - hold',
)

_INT = (
    'int - ready to test',
    'int - testing',
    'int - testing done',
)

_INT_READY = (
    'int - ready to test',
)

_INT_TESTING = (
    'int - testing',
)

_INT_WAITING = (
    'int - testing done',
)

_INT_HOLD = (
    'int - hold',
)

_HOLD = (
    'on hold',
)

_PROD = (
    'deployed to production',
)

_DONE = (
    'passed',
    'failed',
    'closed',
    'done',
)


class ContinueOne(Exception):
    pass


estimation = {  # 1 2 3 5 8 13 20 40 100
    '': 4,
    'Хомяк': 3,
    'Кот': 5,
    'Пингвин': 8,
    'Кенгуру': 13,
    'Бурый медведь': 20,
    'Кит': 40,
}


class JSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super(JSONEncoder, self).default(obj)


def _hours(seconds):
    return floor(seconds / 3600 + 0.5)


def _days(seconds):
    return ceil(seconds / 86400)


def _normal_datetime_str(t_str):
    if t_str is None:
        return None
    return t_str.replace('T', ' ').replace('+03:00', '')


def parse_t_date(str_date):
    return datetime.datetime(
        year=int(str_date[:4]),
        month=int(str_date[5:7]),
        day=int(str_date[8:10]),
        hour=int(str_date[11:13]),
        minute=int(str_date[14:16]),
        second=int(str_date[17:19])
    )


def _diff_in_seconds(str_day1, str_day2):
    return (parser.parse(str_day1) - parser.parse(str_day2)).total_seconds()


def _diff_dt_in_seconds(day1, day2):
    return (day1 - day2).total_seconds()


def parse_sprint_string(sprint):
    sprint = sprint[sprint.find("[") + 1:sprint.rfind("]")]
    _tmp = {}
    for item in sprint.split(','):
        x = item.split('=')
        if len(x) == 1:
            continue
        _tmp[x[0]] = x[1]

    return _tmp


def sprints_from_string(sprint_list):
    _result = []
    for sprint in sprint_list:
        sprint = sprint[sprint.find("[") + 1:sprint.rfind("]")]
        _tmp = {}
        for item in sprint.split(','):
            x = item.split('=')
            if len(x) == 1:
                continue
            _tmp[x[0]] = x[1]

        if _tmp['name'] in _NONE_ACTIVE_BACKLOGS or _tmp['state'] == 'FUTURE':
            continue

        _tmp['startDate'] = parser.parse(_tmp['startDate']) \
            if 'startDate' in _tmp and _tmp['startDate'] != _NULL else None
        _tmp['endDate'] = parser.parse(_tmp['endDate']) \
            if 'endDate' in _tmp and _tmp['endDate'] != _NULL else None
        _result.append(_tmp)

    return _result


# {'бизнес аналитика подготовлена', 'к планингу', 'к груммингу', 'new', 'in progress', 'review - hold', 'prod',
#   'review', 'подготовка системной аналитики', 'done', 'code review', 'testing', 'in progress - hold', 'dev - hold',
#   'reopened', 'passed', 'бизнес анализ', 'deployed to production', 'to develop', 'согласование бизнес аналитики',
#   'int - testing done', 'int - testing', 'on hold', 'closed', 'int testing', 'int - hold', 'to do',
#   'dev - ready to test', 'int - ready to test', 'dev - testing', 'dev - testing done', 'аналитика'}
def get_statuses(changelog, issue_created=None):
    _result = []
    for log_item in changelog:
        item_created = log_item['created']
        try:
            author = log_item['author']['displayName']
        except KeyError:
            author = ''
        for field in log_item['items']:
            if field['field'] == 'status':
                to_field = field['toString'].lower()
                if len(_result) == 0 and issue_created is not None:
                    from_field = field['fromString'].lower()
                    # created = parser.parse(issue_created)
                    # if int(issue_created[8:10]) != created.day or int(issue_created[5:7]) != created.month:
                    #     print(issue_created, created)
                    _result.append({
                        'author': author,
                        'status': from_field,
                        'created': parser.parse(issue_created)
                    })
                # created = parser.parse(issue_created)
                # if int(issue_created[8:10]) != created.day or int(issue_created[5:7]) != created.month:
                #     print(issue_created, created)
                _result.append({
                    'author': author,
                    'status': to_field,
                    'created': parser.parse(item_created)
                })
    all_statuses = _result
    all_statuses.append(None)

    for previous, current in zip(all_statuses, all_statuses[1:]):
        previous['next'] = copy(current)

    return all_statuses[:-1]


def get_fields_changelog(changelog, field_names):
    _result = []
    for log_item in changelog:
        item_created = log_item['created']
        try:
            author = log_item['author']['displayName']
        except KeyError:
            author = ''
        for field in log_item['items']:
            if field['field'] in field_names:
                to_field = field['toString'].lower()
                from_field = field['fromString'].lower() if 'fromString' in field and field['fromString'] else ''
                _result.append({
                    'author': author,
                    'field': field['field'],
                    'from': from_field,
                    'to': to_field,
                    'created': parser.parse(item_created)
                })

    return _result


# customfield_43585 – analisys
# customfield_43586 – front
# customfield_43587 – middle
# customfield_43588 – pega
# customfield_43589 – test
def get_stack_sp(changelog, issue_created=None):
    _result = {}
    for k in _STACKS:
        _result[k] = []

    for log_item in changelog:
        item_created = log_item['created']
        try:
            author = log_item['author']['displayName']
        except KeyError:
            author = ''
        for field in log_item['items']:
            stack = field['field'].lower().replace('sp ', '')
            if stack in _STACKS:
                to_field = float(field['toString'] if field['toString'] else 0)
                from_field = float(field['fromString'] if field['fromString'] else 0)
                _result[stack].append({
                    'author': author,
                    'value_from': from_field,
                    'value_to': to_field,
                    'created': parser.parse(item_created)
                })

    return _result


def get_releases(changelog):
    _result_added = []
    _result_removed = []
    for log_item in changelog:
        item_created = log_item['created']
        for field in log_item['items']:
            if field['field'] == 'Fix Version':
                if field['to']:
                    _result_added.append({
                        'id': field['to'].lower(),
                        'name': field['toString'].lower(),
                        'created': parser.parse(item_created)
                    })
                else:
                    _result_removed.append({
                        'id': field['from'].lower(),
                        'name': field['fromString'].lower(),
                        'created': parser.parse(item_created)
                    })

    return {
        'added': _result_added,
        'removed': _result_removed
    }


def get_affects(changelog):
    _result_added = []
    _result_removed = []
    for log_item in changelog:
        item_created = log_item['created']
        for field in log_item['items']:
            if field['field'] == 'Version':
                if field['to']:
                    _result_added.append({
                        'id': field['to'].lower(),
                        'name': field['toString'].lower(),
                        'created': parser.parse(item_created)
                    })
                else:
                    _result_removed.append({
                        'id': field['from'].lower(),
                        'name': field['fromString'].lower(),
                        'created': parser.parse(item_created)
                    })

    return {
        'added': _result_added,
        'removed': _result_removed
    }


def filter_statuses(statuses, status_names):
    return filter(lambda x: x['status'] in status_names, statuses)


def first_in_progress(statuses):
    return min(filter_statuses(statuses, _STATUS_IN_PROGRESS), key=lambda x: x['created'])


def last_finished(statuses):
    return max(filter_statuses(statuses, _STATUSES_FINISHED), key=lambda x: x['created'])


def is_in_status(statuses, status_names):
    return len(list(filter_statuses(statuses, status_names))) > 0


def first_in_status(statuses, status_names):
    return min(filter_statuses(statuses, status_names), key=lambda x: x['created'])


def last_in_status(statuses, status_names):
    return max(filter_statuses(statuses, status_names), key=lambda x: x['next']['created'])


def last_to_status(statuses, status_names):
    return max(filter_statuses(statuses, status_names), key=lambda x: x['created'])


def first_sprint(sprints):
    return min(filter(lambda x: x['startDate'] is not None, sprints), key=lambda x: x['startDate'])


def last_sprint(sprints):
    return max(filter(lambda x: x['endDate'] is not None, sprints), key=lambda x: x['endDate'])


def get_dev_subtasks(subtasks):
    return filter(
        lambda x: x['issuetype'] in _DEV_TASKS
                  and not x['summary'].lower().startswith('оповещение')
                  and not x['summary'].lower().startswith('дизайн')
                  and not x['summary'].lower().startswith('са'),
        subtasks
    )


def get_finished_dev_subtasks(subtasks):
    return filter(
        lambda x: len(list(filter(lambda y: y['status'] in _STATUSES_FINISHED, x['statuses']))) > 0,
        get_dev_subtasks(subtasks)
    )


def get_dev_subtasks_statuses(subtasks):
    return reduce(lambda a, b: a + b, map(lambda x: x['statuses'], get_dev_subtasks(subtasks)))


def get_linked_issues(issuelinks):
    return issuelinks


def get_rebuild_count(issue):
    # найти сабтаску с назнанием CLMProd
    _clmprod = list(filter(lambda x: x['summary'] == 'CLMProd', issue['subtasks']))
    if len(_clmprod) == 0:
        print(issue['key'], 'нет сабтаски с названием CLMProd')
        return None

    # найти в истории дескрипшены с RCn
    _result = []
    for log_item in _clmprod[0]['history']:
        for field in log_item['items']:
            if field['field'] == 'description':
                _result = _result + re.findall('_RC(\d+).zip', field['toString'])

    # вернуть n у последнего изменения или None
    if len(_result) > 0:
        return max(_result)
    return 0


def is_yes_value(field) -> bool:
    if field and 'value' in field and field['value'] == 'Да':
        return True
    else:
        return False


def normalize_issue(issue):
    est = ''
    if 'customfield_21771' in issue['fields'] and issue['fields']['customfield_21771']:
        est = issue['fields']['customfield_21771']['value']
    sprints = sprints_from_string(issue['fields']['customfield_10375'])
    if not sprints:
        return None

    issue_created = issue['fields']['created'] if issue['fields']['created'] else None
    statuses = get_statuses(issue['changelog']['histories'], issue_created)
    created = parser.parse(issue_created) if issue_created else ''

    if 'parent' in issue['fields']:
        promised = created
    else:
        try:
            promised = min((first_in_progress(statuses)['created'], first_sprint(sprints)['startDate']))
        except ValueError:
            promised = first_sprint(sprints)['startDate']
        promised = max(created, promised)

    subtasks_keys = []
    if 'subtasks' in issue['fields']:
        for subtask in issue['fields']['subtasks']:
            subtasks_keys.append(subtask['key'])

    ls = last_sprint(sprints)
    if ls['state'] != 'CLOSED':
        ls = None
    try:
        lf = last_finished(statuses)
    except ValueError:
        lf = None

    if ls is not None and lf is not None:
        finished = min((lf['created'], ls['endDate']))
    elif lf is not None:
        finished = lf['created']
    else:
        finished = None

    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        'parent': issue['fields']['parent']['key'] if 'parent' in issue['fields'] else None,
        'epic_key': issue['fields']['customfield_10376'] if 'customfield_10376' in issue['fields'] else None,
        'Relative estimation': est,
        'SP': estimation[est],
        'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else '',
        'reporter': issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else '',
        'created': created,
        'promised': promised,
        'finished': finished,
        'was_done': bool(list(filter(lambda x: x['status'] == _STATUS_DONE, statuses))),
        'labels': ', '.join(issue['fields']['labels']),
        'sprints': sprints,
        'subtasks_keys': subtasks_keys if subtasks_keys else None,
        'statuses': statuses,
        'status': issue['fields']['status']['name']
    }


def normalize_full_clm_issue(issue):
    sprints = sprints_from_string(issue['fields']['customfield_10375'])
    if not sprints:
        return None
    statuses = get_statuses(issue['changelog']['histories'])
    releases = get_releases(issue['changelog']['histories'])
    affects = get_affects(issue['changelog']['histories'])

    created = parser.parse(issue['fields']['created']) if issue['fields']['created'] else ''

    if 'parent' in issue['fields']:
        promised = created
    else:
        try:
            promised = min((first_in_progress(statuses)['created'], first_sprint(sprints)['startDate']))
        except ValueError:
            promised = first_sprint(sprints)['startDate']
        promised = max(created, promised)

    subtasks_keys = []
    if 'subtasks' in issue['fields']:
        for subtask in issue['fields']['subtasks']:
            subtasks_keys.append(subtask['key'])

    ls = last_sprint(sprints)
    if ls['state'] != 'CLOSED':
        ls = None
    try:
        lf = last_finished(statuses)
    except ValueError:
        lf = None

    if ls is not None and lf is not None:
        finished = min((lf['created'], ls['endDate']))
    elif lf is not None:
        finished = lf['created']
    else:
        finished = None

    fix_version = None
    affects_version = None

    if 'fixVersions' in issue['fields'] and len(issue['fields']['fixVersions']) > 0:
        fix_version = issue['fields']['fixVersions'][0]
        if len(issue['fields']['fixVersions']) > 1:
            # если вывелось хоть что-то, продумать как дейстововать тогда
            print(issue['key'], len(issue['fields']['fixVersions']), 'fixVersions продумать как дейстововать!')

        fix_version['added'] = None
        for x in releases['added']:
            if x['id'] == fix_version['id']:
                fix_version['added'] = x['created']

    if 'versions' in issue['fields'] and len(issue['fields']['versions']) > 0:
        affects_version = issue['fields']['versions'][0]
        if len(issue['fields']['versions']) > 1:
            # если вывелось хоть что-то, продумать как дейстововать тогда
            print(issue['key'], len(issue['fields']['versions']), 'affects_version продумать как дейстововать!')

        affects_version['added'] = None
        for x in affects['added']:
            if x['id'] == affects_version['id']:
                affects_version['added'] = x['created']

    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        'parent': issue['fields']['parent']['key'] if 'parent' in issue['fields'] else None,
        'epic_key': issue['fields']['customfield_10376'] if 'customfield_10376' in issue['fields'] else None,
        'SP': issue['fields']['customfield_10372'],
        'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else '',
        'reporter': issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else '',
        'created': created,
        'promised': promised,
        'finished': finished,
        'duedate': issue['fields']['customfield_21470'] if 'customfield_21470' in issue['fields'] else None,
        'fix_version': fix_version,
        'affects_version': affects_version,
        'releases': releases,
        'affects': affects,
        'history': issue['changelog']['histories'],
        'was_done': bool(list(filter(lambda x: x['status'] == _STATUS_DONE, statuses))),
        'labels': ', '.join(issue['fields']['labels']),
        'sprints': sprints,
        'subtasks_keys': subtasks_keys if subtasks_keys else None,
        'statuses': statuses,
        'status': issue['fields']['status']['name']
    }


def normalize_epic_issue(issue):
    statuses = get_statuses(issue['changelog']['histories'])

    created = parser.parse(issue['fields']['created']) if issue['fields']['created'] else ''

    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        'parent': issue['fields']['parent']['key'] if 'parent' in issue['fields'] else None,
        'epic_key': issue['fields']['customfield_10376'] if 'customfield_10376' in issue['fields'] else None,
        'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else '',
        'reporter': issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else '',
        'created': created,
        'was_done': bool(list(filter(lambda x: x['status'] == _STATUS_DONE, statuses))),
        'labels': ', '.join(issue['fields']['labels']),
        'statuses': statuses,
        'status': issue['fields']['status']['name']
    }


def normalize_interview_issue(issue):
    statuses = get_statuses(issue['changelog']['histories'])

    created = parser.parse(issue['fields']['created']) if issue['fields']['created'] else ''

    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        'parent': issue['fields']['parent']['key'] if 'parent' in issue['fields'] else None,
        'epic_key': issue['fields']['customfield_10376'] if 'customfield_10376' in issue['fields'] else None,
        'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else '',
        'reporter': issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else '',
        'created': created,
        'was_done': bool(list(filter(lambda x: x['status'] == _STATUS_DONE, statuses))),
        'labels': ', '.join(issue['fields']['labels']),
        'statuses': statuses,
        'status': issue['fields']['status']['name']
    }


def normalize_simple_clm_issue(issue):
    sprints = sprints_from_string(issue['fields']['customfield_10375']) \
        if issue['fields']['customfield_10375'] is not None else []
    issue_created = issue['fields']['created'] if issue['fields']['created'] else None
    statuses = get_statuses(issue['changelog']['histories'], issue_created)
    created = parser.parse(issue['fields']['created']) if issue['fields']['created'] else ''

    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        # 'parent': {
        #     'key': issue['fields']['parent']['key'] if 'parent' in issue['fields'] else None,
        #     'summary': issue['fields']['parent']['fields']['summary'] if 'parent' in issue['fields'] else None,
        # },
        'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else '',
        'reporter': issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else '',
        'created': created,
        # 'sprints': sprints,
        'statuses': statuses,
        'status': issue['fields']['status']['name']
    }


def normalize_ksm_issue(issue):
    issue_created = issue['fields']['created'] if issue['fields']['created'] else None
    created = parser.parse(issue_created) if issue_created else ''

    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        'project': issue['fields']['project']['key'],
        'project_name': issue['fields']['project']['name'],
        'project_category': issue['fields']['project']['projectCategory']['name'],
        'epic_key': issue['fields']['customfield_10376'] if 'customfield_10376' in issue['fields'] else None,
        'epic_name': issue['fields']['customfield_10377'] if 'customfield_10377' in issue['fields'] else None,
        'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else '',
        'reporter': issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else '',
        'created': created,
        'ppm': issue['fields']['customfield_35298'] if 'customfield_35298' in issue['fields'] else None,
        'kp': issue['fields']['customfield_40171'] if 'customfield_40171' in issue['fields'] else None,
        'status': issue['fields']['status']['name'],
        'status_category': issue['fields']['status']['statusCategory']['name'],
        'linked_issues': get_linked_issues(issue['fields']['issuelinks'])
    }


def normalize_simple_issue(issue):
    issue_created = issue['fields']['created'] if issue['fields']['created'] else None
    statuses = get_statuses(issue['changelog']['histories'], issue_created)
    created = parser.parse(issue_created) if issue_created else ''

    subtasks_keys = []
    if 'subtasks' in issue['fields']:
        for subtask in issue['fields']['subtasks']:
            subtasks_keys.append(subtask['key'])

    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'is_subtask': issue['fields']['issuetype']['subtask'],
        'summary': issue['fields']['summary'],
        'parent': issue['fields']['parent']['key'] if 'parent' in issue['fields'] else None,
        'epic_key': issue['fields']['customfield_10376'] if 'customfield_10376' in issue['fields'] else None,
        'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else '',
        'reporter': issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else '',
        'created': created,
        'was_done': bool(list(filter(lambda x: x['status'] == _STATUS_DONE, statuses))),
        'labels': ', '.join(issue['fields']['labels']),
        'statuses': statuses,
        'history': issue['changelog']['histories'],
        'subtasks_keys': subtasks_keys if subtasks_keys else None,
        'status': issue['fields']['status']['name'],
        'status_category': issue['fields']['status']['statusCategory']['name'],
    }


def get_sprints_from_issue(issue):
    return sprints_from_string(issue['fields']['customfield_10375']) \
        if issue['fields']['customfield_10375'] is not None else []


def normalize_issue_with_sprints(issue):
    result = normalize_simple_issue(issue)
    result['sprints'] = get_sprints_from_issue(issue)
    result['epic_name'] = issue['fields']['customfield_10377'] if 'customfield_10377' in issue['fields'] else None,
    result['stream'] = issue['fields']['customfield_44480'] if 'customfield_44480' in issue['fields'] else None,
    return result


def normalize_issue_with_comments(issue):
    result = normalize_simple_issue(issue)
    result['comments'] = issue['comments']
    return result


def normalize_issue_with_SP(issue):
    result = normalize_simple_issue(issue)
    result['SP'] = issue['fields']['customfield_10372']
    return result


def normalize_oleg_issue(issue):
    result = normalize_simple_issue(issue)
    result['assignee'] = issue['fields']['assignee'] if issue['fields']['assignee'] else None
    result['reporter'] = issue['fields']['reporter'] if issue['fields']['reporter'] else None
    return result


def normalize_onaplan_issue(issue):
    result = normalize_simple_issue(issue)
    _f = issue['fields']
    result['plan_type'] = _f['customfield_43590']['value'] if 'customfield_43590' in _f and _f['customfield_43590'] else None
    result['stream'] = _f['customfield_44480']['value'] if 'customfield_44480' in _f and _f['customfield_44480'] else None
    result['p1'] = _f['customfield_43570']['value'] if 'customfield_43570' in _f and _f['customfield_43570'] else None
    result['p2'] = _f['customfield_43571']['value'] if 'customfield_43571' in _f and _f['customfield_43571'] else None
    result['p3'] = _f['customfield_43572']['value'] if 'customfield_43572' in _f and _f['customfield_43572'] else None
    result['p4'] = _f['customfield_43573']['value'] if 'customfield_43573' in _f and _f['customfield_43573'] else None
    result['f1'] = _f['customfield_43574']['value'] if 'customfield_43574' in _f and _f['customfield_43574'] else None
    result['f2'] = _f['customfield_43575']['value'] if 'customfield_43575' in _f and _f['customfield_43575'] else None
    result['f3'] = _f['customfield_43576']['value'] if 'customfield_43576' in _f and _f['customfield_43576'] else None
    result['f4'] = _f['customfield_43577']['value'] if 'customfield_43577' in _f and _f['customfield_43577'] else None
    return result


def normalize_onaplan_with_sprints(issue):
    result = normalize_onaplan_issue(issue)
    _f = issue['fields']
    result['sprints'] = get_sprints_from_issue(issue)
    result['duedate'] = _f['duedate'] if 'duedate' in _f and _f['duedate'] else None
    issue_created = _f['created'] if _f['created'] else None
    stack_sp = get_stack_sp(issue['changelog']['histories'], issue_created)
    result['stack_sp'] = stack_sp
    result['resolution'] = _f['resolution']['name'] if 'resolution' in _f and _f['resolution'] and 'name' in _f['resolution'] else None
    result['resolutiondate'] = _f['resolutiondate'] if 'resolutiondate' in _f and _f['resolutiondate'] else None
    _c = _f['customfield_24371'] if 'customfield_24371' in _f else None
    result['customer'] = {_k: _c.get(_k) for _k in ['name', 'emailAddress','displayName', 'active']} \
        if 'customfield_24371' in _f and _f['customfield_24371'] and 'name' in _f['customfield_24371'] else None
    return result


def get_emp_links(links):
    result = []
    for item in links:
        if item['type']['name'] == 'Connected with':
            if 'outwardIssue' in item:
                result.append(item['outwardIssue']['fields']['summary'])
            else:
                result.append(item['inwardIssue']['fields']['summary'])

    return result


def get_all_issue_links(links):
    result = []
    for item in links:
        _tmp = {'link_type': item['type']}
        if 'outwardIssue' in item:
            _tmp.update(normalize_tiny_issue(item['outwardIssue']))
        else:
            _tmp.update(normalize_tiny_issue(item['inwardIssue']))
        result.append(_tmp)

    return result


def normalize_teams_issue(issue):
    result = normalize_tiny_issue(issue)
    result['KP'] = issue['fields']['customfield_24778']['value'] if issue['fields']['customfield_24778'] else None
    result['line'] = issue['fields']['customfield_33475']['value'] if issue['fields']['customfield_33475'] else None
    result['SM'] = issue['fields']['customfield_45307']['displayName'] if issue['fields']['customfield_45307'] else None
    result['TSM'] = issue['fields']['customfield_45308']['displayName'] if issue['fields'][
        'customfield_45308'] else None
    result['IT_type'] = issue['fields']['customfield_19574']['value'] if 'customfield_19574' in issue[
        'fields'] else None
    result['jira_project'] = issue['fields']['customfield_36707'] if issue['fields']['customfield_36707'] else None
    result['employees'] = get_emp_links(issue['fields']['issuelinks'])
    return result


def normalize_teams2_issue(issue):
    result = normalize_tiny_issue(issue)
    _f = issue['fields']
    result['KP'] = _f['customfield_24778']['value'] if _f['customfield_24778'] else None
    result['bus_line'] = _f['customfield_19575']['value'] if 'customfield_19575' in _f and _f['customfield_19575'] else None
    result['line'] = _f['customfield_33475']['value'] if _f['customfield_33475'] else None
    result['SM'] = _f['customfield_45307']['displayName'] if _f['customfield_45307'] else None
    result['TSM'] = _f['customfield_45308']['displayName'] if _f[
        'customfield_45308'] else None
    result['IT_type'] = _f['customfield_19574']['value'] if 'customfield_19574' in _f else None
    result['jira_project'] = _f['customfield_36707'] if _f['customfield_36707'] else None
    result['ppm'] = _f['customfield_35293'] if _f['customfield_35293'] else None
    result['employees'] = get_all_issue_links(_f['issuelinks'])
    return result


def normalize_issue_with_stack_sp(issue):
    result = normalize_issue_with_sprints(issue)
    issue_created = issue['fields']['created'] if issue['fields']['created'] else None
    stack_sp = get_stack_sp(issue['changelog']['histories'], issue_created)
    result['stack_sp'] = stack_sp
    return result


def normalize_tiny_issue(issue):
    return {
        'key': issue['key'],
        'issuetype': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        'status': issue['fields']['status']['name'],
        'status_category': issue['fields']['status']['statusCategory']['name'],
    }


def normalize_brd_issue(issue):
    result = normalize_simple_issue(issue)
    result['links'] = get_all_issue_links(issue['fields']['issuelinks'])
    return result


def normalize_emp_issue(issue):
    result = normalize_tiny_issue(issue)
    _f = issue['fields']
    result['employee'] = _f['customfield_13070']
    result['u_id'] = _f['customfield_13070']['name'] if _f['customfield_13070'] else None
    result['email'] = _f['customfield_13070']['emailAddress'] if _f['customfield_13070'] else None
    result['fio'] = _f['customfield_13070']['displayName'] if _f['customfield_13070'] else None
    result['active'] = _f['customfield_13070']['active'] if _f['customfield_13070'] else None
    result['position'] = _f['customfield_19876']['value'] if _f['customfield_19876'] else None
    result['registration'] = _f['customfield_12375']['value'] if 'customfield_12375' in _f else None
    # подумать про map/reduce всё в одно значение, все департаменты и отделы в одну строчку сложить,
    # пока беру только последнее значение в массиве
    result['department'] = _f['customfield_22376'][-1]['value'] \
        if _f['customfield_22376'] and len(_f['customfield_22376']) else None
    result['table_number'] = _f['customfield_45571'] if _f['customfield_45571'] else None
    result['archetype'] = _f['customfield_34077']['value'] if _f['customfield_34077'] else None
    result['epath'] = get_all_issue_links(_f['issuelinks'])
    return result


def normalize_eteam_issue(issue):
    result = normalize_tiny_issue(issue)
    _f = issue['fields']
    result['percentage'] = _f['customfield_50272']
    result['KP'] = _f['customfield_24778']['value'] if _f['customfield_24778'] else None
    result['role'] = _f['customfield_46377']['value'] if _f['customfield_46377'] else None
    return result


def normalize_ppm_issue(issue):
    _f = issue['fields']
    result = normalize_tiny_issue(issue)
    result['links'] = get_all_issue_links(_f['issuelinks']) if 'issuelinks' in _f and _f['issuelinks'] else None
    result['master_ppm'] = _f['customfield_47475'] \
        if 'customfield_47475' in _f and _f['customfield_47475'] else None
    if result['master_ppm']:
        _s = re.findall('<a[^>]*>(.*)<\/a>', result['master_ppm'])
        result['master_ppm'] = _s[0] if _s else result['master_ppm']
    result['ppm_object'] = _f['customfield_47272'] if 'customfield_47272' in _f and _f['customfield_47272'] else None
    return result


def normalize_kr_issue(issue):
    result = normalize_tiny_issue(issue)

    _f = issue['fields']
    issue_created = _f['created'] if _f['created'] else None

    result['links'] = get_all_issue_links(_f['issuelinks'])
    # customfield_21675 – Estimated start date
    result['estimated_start_date'] = _f['customfield_21675'] if _f['customfield_21675'] else None
    # customfield_21471 – Estimated completion date
    result['estimated_completion_date'] = _f['customfield_21471'] if _f['customfield_21471'] else None
    # customfield_58872 – WOW
    result['is_wow'] = is_yes_value(_f['customfield_58872'])
    # customfield_50270 – Включен в мастер-план
    result['is_MP'] = is_yes_value(_f['customfield_50270'])

    result['created'] = parser.parse(issue_created) if issue_created else ''
    result['statuses'] = get_statuses(issue['changelog']['histories'], issue_created)

    return result


def normalize_epic2_issue(issue):
    result = normalize_tiny_issue(issue)

    _f = issue['fields']
    issue_created = _f['created'] if _f['created'] else None
    result['assignee'] = _f['assignee']['displayName'] if _f['assignee'] else '',
    result['reporter'] = _f['reporter']['displayName'] if _f['reporter'] else '',

    result['links'] = get_all_issue_links(_f['issuelinks']) if 'issuelinks' in _f else None
    # customfield_21675 – Estimated start date
    result['estimated_start_date'] = _f['customfield_21675'] if _f['customfield_21675'] else None
    # customfield_21471 – Estimated completion date
    result['estimated_completion_date'] = _f['customfield_21471'] if _f['customfield_21471'] else None
    # customfield_40171 – Ключевой Результат
    result['kr'] = _f['customfield_40171'] if 'customfield_40171' in _f else None

    result['created'] = parser.parse(issue_created) if issue_created else ''
    result['statuses'] = get_statuses(issue['changelog']['histories'], issue_created)
    result['history'] = issue['changelog']['histories'] if 'changelog' in issue and 'histories' in issue['changelog'] else None

    return result


def normalize_small_issue(issue):
    result = normalize_tiny_issue(issue)
    _f = issue['fields']
    result.update({
        'epic_key': _f['customfield_10376'] if 'customfield_10376' in _f else None,
        'assignee': _f['assignee']['displayName'] if _f['assignee'] else '',
        'reporter': _f['reporter']['displayName'] if _f['reporter'] else '',
        'created': _f['created'] if _f['created'] else None,
        'labels': ', '.join(_f['labels']),
        'history': issue['changelog']['histories'],
    })
    return result


def normalize_issue_with_component(issue):
    result = normalize_small_issue(issue)
    _f = issue['fields']
    result['component'] = _f['components'] if 'components' in _f else None
    result['sprint'] = _f['customfield_10375'] if 'customfield_10375' in _f else None
    return result


# def merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
def merge_intervals(intervals):
    """Объединяет пересекающиеся интервалы времени."""
    if not intervals:
        return []

    # Сортируем интервалы по времени начала
    intervals.sort()
    merged = [intervals[0]]

    for current_start, current_end in intervals[1:]:
        last_start, last_end = merged[-1]

        if current_start <= last_end:  # Есть пересечение
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))

    return merged


def calculate_time_in_status(all_issues: List[Dict], target_statuses: Tuple[str, ...], done_statuses: Tuple[str, ...]) -> int:
    """
    Вычисляет общее время (в секундах), которое задачи находились в указанных статусах,
    учитывая пересечения.

    :param all_issues: Список задач с их статусами.
    :param target_statuses: Кортеж названий статусов, для которых нужно вычислить время.
    :param done_statuses: Кортеж статусов, которые считаются финальными.
    :return: Общее время в секундах.
    """
    intervals = []

    for issue in all_issues:
        statuses = issue.get('statuses', [])

        for status_entry in statuses:
            if status_entry['status'] in target_statuses:
                start_time = parser.parse(status_entry['created'])

                # Проверяем, есть ли следующий статус
                next_status = status_entry.get('next')
                if next_status:
                    end_time = parser.parse(next_status['created'])

                    # Пропускаем, если следующий статус финальный
                    if next_status['status'] in done_statuses:
                        continue
                else:
                    # Если следующего статуса нет, пропускаем
                    continue

                intervals.append((start_time, end_time))

    # Удаляем пересечения интервалов
    merged_intervals = merge_intervals(intervals)

    # Вычисляем общее время
    total_seconds = sum((end - start).total_seconds() for start, end in merged_intervals)
    return int(total_seconds)