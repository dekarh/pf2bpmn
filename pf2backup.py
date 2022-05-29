import time
from datetime import datetime
import requests
import json
import os
import csv
from sys import argv, exit
import xmltodict

from hide_data import USR_Tocken, PSR_Tocken, PSR_Tocken2, PF_ACCOUNT

URL = "https://apiru.planfix.ru/xml"
PF_HEADER = {"Accept": 'application/xml', "Content-Type": 'application/xml'}
PF_BACKUP_DIRECTORY = '../pf_data/loading/current'


class EscapeFromThread(Exception):
    print("Выход из треда")

def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    if total == 0:
        total = 1
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = '\r')
    # Print New Line on Complete
    if iteration == total:
        print()

def api_load_from_point(api_method, api_request, psr=PSR_Tocken):
    global limit_overflow
    if not limit_overflow:
        i_err = 0
        while True:
            answertext = ''
            if i_err > 10:
                break
            try:
                answer = requests.post(
                    URL,
                    headers=PF_HEADER,
                    data=('<request method="' + api_method + '"><account>' + PF_ACCOUNT + '</account>'
                          + api_request + '</request>').encode(),
                    auth=(USR_Tocken, psr)
                )
                answertext = answer.text
                if xmltodict.parse(answer.text)['response']['@status'] == 'error':
                    print('\nСБОЙ №', i_err, 'в', process, '\nпараметры:', api_request, '\n',
                          answer.text)
                    if xmltodict.parse(answer.text)['response']['code'] == '0007':
                        limit_overflow = True
                        print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                                                        'Превышено 50000 обращений в день к АПИ')
                        exit(2)
                    elif xmltodict.parse(answer.text)['response']['code'] == '0015':
                        print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'), 'Ошибка 0015')
                        exit(2)
                    elif xmltodict.parse(answer.text)['response']['code'] == '3001':
                        return ''
                    elif xmltodict.parse(answer.text)['response']['code'] == '3014':
                        print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                              'Задача в процессе изменения (сценарием или другим запросом)')
                        i_err += 1
                        time.sleep(1)
                        continue
                    else:
                        i_err += 1
                        continue
                elif not answer.ok:
                    i_err += 1
                    continue
                else:
                    if str(type(xmltodict.parse(answer.text)['response']['task'])).replace("'", '') \
                            == '<class NoneType>':
                        i_err += 1
                        continue
                    else:
                        return answer.text
            except Exception as e:
                print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'), 'ОШИБКА:', e, '\nпараметры:',
                      api_request, '\n', answertext)
                exit(2)
    exit(2)

def api_load_from_list(api_method, objs_name, obj_name, file_name, api_additionally='',
                       pagination=True, res_dict=None, with_totalcount=True, key_name='id', psr=PSR_Tocken):
    """
    api_method - название загружаемого метода, напр. task.getList
    obj_name - название типа загружаемого объекта в АПИ
    file_name - имя сохраняемого файла
    api_additionally - дополнительные ключи АПИ напр. <target>all</target>
    pagination - есть деление на страницы
    res_dict - словарь с ранее загруженной информацией
    with_totalcount - есть/нет @TotalCount
    key_name - имя идентификатора (id или key)
    """
    global limit_overflow
    global request_count
    if limit_overflow:
        print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'), 'Превышено 50000 обращений в день к АПИ')
        exit(2)
    if res_dict is None:
        res_dict = {}
    i = 1
    obj_total_count = 1000
    obj_count = 0
    if len(argv) == 1 and with_totalcount and file_name:
        printProgressBar(obj_count, obj_total_count + 1, prefix='Скачано ' + api_method + ':', suffix=obj_name,
                         length=50)
        boost = '\n'
    else:
        boost = ''
    continuation = True
    has_pages = True
    answertext = ''
    try:
        while continuation:
            i_err = 0
            while True:
                answertext = ''
                if i_err > 10:
                    if not pagination:
                        continuation = False
                    elif not has_pages:
                        continuation = False
                    break
                objs_loaded = []
                request_count += 1
                try:
                    if pagination:
                        answer = requests.post(
                            URL,
                            headers=PF_HEADER,
                            data='<request method="' + api_method + '"><account>' + PF_ACCOUNT
                                 + '</account>' + api_additionally + '<pageSize>100</pageSize><pageCurrent>'
                                 + str(i) + '</pageCurrent></request>',
                            auth=(USR_Tocken, psr)
                        )
                    else:
                        answer = requests.post(
                            URL,
                            headers=PF_HEADER,
                            data='<request method="' + api_method + '"><account>' + PF_ACCOUNT
                                 + '</account>' + api_additionally + '</request>',
                            auth=(USR_Tocken, psr)
                        )
                    answertext = answer.text
                    if not answer.ok:
                        i_err += 1
                        continue
                    elif answer.text.find('count="0"/></response>') > -1:
                        continuation = False
                        break
                    elif xmltodict.parse(answer.text)['response']['@status'] == 'error':
                        has_pages = False
                        print('\nСБОЙ №', i_err, 'в', api_method, '\nпараметры:', api_additionally, '\n', answer.text)
                        if xmltodict.parse(answer.text)['response']['code'] == '0007':
                            continuation = False
                            limit_overflow = True
                            print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                                                          'Превышено 50000 обращений в день к АПИ')
                            exit(2)
                        elif xmltodict.parse(answer.text)['response']['code'] == '0015':
                            continuation = False
                            print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'), 'Ошибка 0015')
                            exit(2)
                        elif xmltodict.parse(answer.text)['response']['code'] == '3014':
                            print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                                  'Задача в процессе изменения (сценарием или другим запросом)')
                            i_err += 1
                            time.sleep(1)
                            continue
                        else:
                            i_err += 1
                            continue
                    else:
                        if str(type(xmltodict.parse(answer.text)['response'][objs_name])).replace("'", '') \
                                == '<class NoneType>':
                            continuation = False
                            break
                        elif str(type(xmltodict.parse(answer.text)['response'][objs_name][obj_name])).replace("'", '') \
                                == '<class NoneType>':
                            i_err += 1
                            continue
                        elif str(type(xmltodict.parse(answer.text)['response'][objs_name][obj_name])).replace("'", '') \
                                == '<class list>':
                            objs_loaded = xmltodict.parse(answer.text)['response'][objs_name][obj_name]
                            obj_count += len(objs_loaded)
                            objs_str = []
                            debug1 = """
                            for obj_loaded in objs_loaded:
                                objs_str.append(str(obj_loaded.get('id', 'нет')))
                            print('\n       ', ' '.join(objs_str))
                            """
                        else:
                            debug2 = """
                            print('\n       ', objs_loaded[0].get('id', 'нет'))
                            """
                            objs_loaded = [xmltodict.parse(answer.text)['response'][objs_name][obj_name]]
                            obj_count += 1
                        if with_totalcount:
                            if obj_total_count == 1000:
                                obj_total_count = int(
                                    xmltodict.parse(answer.text)['response'][objs_name]['@totalCount'])
                        for obj in objs_loaded:
                            res_dict[int(obj[key_name])] = obj
                        if not pagination:
                            continuation = False
                        break
                except Exception as e:
                    print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'), 'ОШИБКА:', e, 'в', api_method,
                          '\nпараметры:', api_additionally, '\n', answertext)
                    if not pagination:
                        continuation = False
                    break
            if len(argv) == 1 and with_totalcount and file_name:
                printProgressBar(obj_count, obj_total_count + 1, prefix='Скачано ' + api_method + ':', suffix=obj_name,
                                 length=50)
            i += 1
    finally:
        if file_name:
            with open(os.path.join(
                    PF_BACKUP_DIRECTORY,
                    list(map(lambda x:'part-' if x else '', [limit_overflow]))[0] + file_name
            ), 'w') as write_file:
                json.dump(res_dict, write_file, ensure_ascii=False)
                print(boost, datetime.now().strftime('%d.%m.%Y %H:%M:%S'), '|',request_count, '|',
                      list(map(lambda x: 'ЧАСТИЧНО' if x else '',[limit_overflow]))[0], 'Сохранено ', len(res_dict),
                      'объектов', obj_name, 'запрошенных методом', api_method)
    return res_dict


if __name__ == "__main__":
    limit_overflow = False
    request_count = 0
    processes_bpmn = {}
    with open(os.path.join(PF_BACKUP_DIRECTORY, 'processes_bpmn.json'), 'r') as read_file:
        processes_loaded = json.load(read_file)
    for process in processes_loaded:
        processes_bpmn[int(process)] = processes_loaded[process]



    print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
          'Загружаем список процессов, статусов, шаблонов, проектов и юзеров')
    processes = {}
    with open(os.path.join(PF_BACKUP_DIRECTORY, 'processes_full.json'), 'r') as read_file:
        processes_loaded = json.load(read_file)
    for process in processes_loaded:
        processes[int(process)] = processes_loaded[process]
    statuses = {}
    with open(os.path.join(PF_BACKUP_DIRECTORY, 'statuses_flectra.json'), 'r') as read_file:
        statuses_loaded = json.load(read_file)
    for status in statuses_loaded:
        statuses[int(str(status)[3:])] = statuses_loaded[status]
        if str(type(statuses_loaded[status].get('project_ids', None))).replace("'","") == '<class list>':
            project_ids = statuses_loaded[status]['project_ids']
            statuses[int(str(status)[3:])]['project_ids'] = []
            for project_id in project_ids:
                statuses[int(str(status)[3:])]['project_ids'].append(int(project_id[3:]))
        else:
            statuses[int(str(status)[3:])]['project_ids'] = []
    tasktemplates = {}
    with open(os.path.join(PF_BACKUP_DIRECTORY, 'tasktemplates_full.json'), 'r') as read_file:
        tasktemplates_loaded = json.load(read_file)
    for tasktemplate in tasktemplates_loaded:
        tasktemplates[int(tasktemplate)] = tasktemplates_loaded[tasktemplate]
    projectgroups = {}
    with open(os.path.join(PF_BACKUP_DIRECTORY, 'projectgroups_full.json'), 'r') as read_file:
        projectgroups_loaded = json.load(read_file)
    for projectgroup in projectgroups_loaded:
        projectgroups[int(projectgroup)] = projectgroups_loaded[projectgroup]
    users = {}
    with open(os.path.join(PF_BACKUP_DIRECTORY, 'users_full.json'), 'r') as read_file:
        users_loaded = json.load(read_file)
    for user in users_loaded:
        if users_loaded[user]['status'] == 'ACTIVE':
            users[int(user)] = users_loaded[user]

    try:
        for process in processes:
            process_templates = []
            for tasktemplate in tasktemplates:
                if tasktemplates[tasktemplate].get('statusSet'):
                    if int(tasktemplates[tasktemplate]['statusSet']) == process:
                        process_templates.append(tasktemplate)
            if process in [230526]: # len(process_templates) < 5: # 229670 - стандартный, 230634 - для смены на Новую
                processes[process]['threads'] = {}
                processes[process]['task_snapshots'] = {}
                processes[process]['start_members'] = {}
                # Для каждого шаблона процесса
                for process_template in process_templates:
                    # Считываем задачу-шаблон
                    response = api_load_from_point('task.get', '<task><id>' + str(process_template) + '</id></task>')
                    start_members = xmltodict.parse(response)['response']['task']['members']
                    statuses2task_snapshot = {}
                    threads2statuses = [[]]
                    thread_id = -1
                    # Для каждой обнаруженной (в т.ч. во время сканирования) ветки, пока они не закончатся
                    while thread_id < len(threads2statuses):
                        thread_id += 1
                        # Создаем сканирующую задачу от меого имени (далее все действия от имени робота) без участников
                        response = api_load_from_point(
                            'task.add',
                            '<task><template>' + str(process_template) + '</template><title>ТЕСТ № ' + str(thread_id)
                            + '</title><description>Это тестовая задача. Пожалуйста, не обращайте внимания</description>'
                            + '<statusSet>' + str(process) + '</statusSet><members><users></users><groups></groups>'
                            + '</members><customData><customValue><id>107508</id><value>Аванс</value></customValue>'
                            + '<customValue><id>108156</id><value>1</value></customValue></customData></task>',
                            psr=PSR_Tocken2
                        )
                        scan_task_id = int(xmltodict.parse(response)['response']['task']['id'])
                        try:
                            # Добавляем робота и меня в исполнители сканирующей задачи
                            api_load_from_point(
                                'task.update',
                                '<silent>1</silent><task><id>' + str(scan_task_id) + '</id><workers><users><id>5309784</id>'
                                   + '<id>5303022</id></users></workers></task>')
                            # Принимаем задачу сканирования
                            response = api_load_from_point(
                                'task.accept',
                                '<task><id>' + str(scan_task_id) + '</id></task>'
                            )
                            if len(threads2statuses[thread_id]):
                                # Перематываем задачу до статуса с которого началось разветвление
                                for i, status in enumerate(threads2statuses[thread_id]):
                                    if i:
                                        # Добавляем робота и меня в исполнители сканирующей задачи
                                        api_load_from_point(
                                            'task.update',
                                            '<silent>1</silent><task><id>' + str(scan_task_id) + '</id><workers><users><id>5309784</id>'
                                            + '<id>5303022</id></users></workers></task>')
                                        # Обновляем статус сканирующей задачи
                                        api_load_from_point(
                                            'task.update',
                                            '<silent>1</silent><task><id>' + str(scan_task_id) + '</id><status>'
                                            + str(status) + '</status></task>')
                            # Добавляем робота и меня в исполнители сканирующей задачи
                            api_load_from_point(
                                'task.update',
                                '<silent>1</silent><task><id>' + str(scan_task_id) + '</id><workers><users><id>5309784</id><id>5303022</id>'
                                   + '</users></workers></task>')
                            # Считываем сканирующую задачу
                            response = api_load_from_point('task.get', '<task><id>' + str(scan_task_id) + '</id></task>')
                            current_status = int(xmltodict.parse(response)['response']['task']['status'])
                            if not len(threads2statuses[thread_id]):
                                threads2statuses[thread_id].append(current_status)
                            statuses2task_snapshot[current_status] = xmltodict.parse(response)['response']['task']
                            # Считываем варианты смены статусов
                            response = api_load_from_list(
                                'task.getPossibleStatusToChange',
                                'statusList',
                                'status',
                                '',
                                '<task><id>' + str(scan_task_id) + '</id></task>',pagination=False, key_name='value')
                            if not len(response):
                                # Ветка закончилась - нет возможных статусов перехода
                                raise EscapeFromThread
                            for i, status in enumerate(response):
                                if i:
                                    # Добавляем дополнительные варианты для сканирования в будущем
                                    threads2statuses.append(threads2statuses[thread_id][:-1] + [status])
                                else:
                                    # Меняем статус на будущий
                                    threads2statuses[thread_id].append(status)
                                    if status in statuses2task_snapshot.keys():
                                        # Ветка закончилась - повторение статуса (обратная петля)
                                        raise EscapeFromThread
                            while threads2statuses[thread_id][-1] != current_status:
                                # Обновляем статус сканирующей задачи
                                api_load_from_point(
                                    'task.update',
                                    '<silent>1</silent><task><id>' + str(scan_task_id) + '</id><status>'
                                    + str(threads2statuses[thread_id][-1]) + '</status></task>')
                                # Добавляем робота и меня в исполнители сканирующей задачи
                                api_load_from_point(
                                    'task.update',
                                    '<silent>1</silent><task><id>' + str(scan_task_id) + '</id><workers><users><id>5309784</id><id>5303022</id>'
                                    + '</users></workers></task>')
                                # Считываем сканирующую задачу
                                response = api_load_from_point('task.get', '<task><id>' + str(scan_task_id) + '</id></task>')
                                current_status = int(xmltodict.parse(response)['response']['task']['status'])
                                statuses2task_snapshot[current_status] = response
                                # Считываем варианты смены статусов
                                response = api_load_from_list(
                                    'task.getPossibleStatusToChange',
                                    'statusList',
                                    'status',
                                    '',
                                    '<task><id>' + str(scan_task_id) + '</id></task>',
                                    pagination=False, key_name='value', psr=PSR_Tocken2)
                                if not len(response):
                                    # Ветка закончилась - нет возможных статусов перехода
                                    raise EscapeFromThread
                                for i, status in enumerate(response):
                                    if i:
                                        # Добавляем дополнительные варианты для сканирования в будущем
                                        threads2statuses.append(threads2statuses[thread_id][:-1] + [status])
                                    else:
                                        # Меняем статус на будущий
                                        threads2statuses[thread_id].append(status)
                                        if status in statuses2task_snapshot.keys():
                                            # Ветка закончилась - повторение статуса (обратная петля)
                                            raise EscapeFromThread
                        except Exception as e:
                            print(e)
                        finally:
                            # Удаляем задачу сканирования через баг смены процесса в задаче
                            response = api_load_from_point(
                                'task.update',
                                '<silent>1</silent><task><id>' + str(scan_task_id) + '</id><statusSet>230634</statusSet></task>')
                            continue
                    # Сохраняем результаты ветки
                    processes[process]['threads'][process_template] = threads2statuses
                    processes[process]['task_snapshots'][process_template] = statuses2task_snapshot
                    processes[process]['start_members'][process_template] = start_members
                    q=0
    finally:
        with open(os.path.join(PF_BACKUP_DIRECTORY, 'processes_bpmn.json'), 'w') as write_file:
            json.dump(processes, write_file, ensure_ascii=False)
        print('\n', datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
               '==================== Работа скрипта завершена ================')
    q=0








