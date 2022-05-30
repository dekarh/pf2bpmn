import time
from datetime import datetime
import requests
import json
import os
import csv
from sys import argv, exit
import xmltodict
import bpmn_python.bpmn_diagram_rep as diagram
import bpmn_python.bpmn_diagram_layouter as layout
import bpmn_python.bpmn_diagram_visualizer as visualizer
import bpmn_python.bpmn_python_consts as consts

from hide_data import USR_Tocken, PSR_Tocken, PSR_Tocken2, PF_ACCOUNT, DEPARTMENTS, OFFICETOWNS

URL = "https://apiru.planfix.ru/xml"
PF_HEADER = {"Accept": 'application/xml', "Content-Type": 'application/xml'}
PF_BACKUP_DIRECTORY = '../pf_data/loading/current'


class EscapeFromThread(Exception):
    print("Выход из треда")


def count_templates():
    """ ДЛЯ ВНУТРЕННЕЙ ПРОВЕРКИ - Перечисление id шаблонов, привязанных к процессу """
    templates_count = {}
    for process in processes:
        for tasktemplate in tasktemplates:
            if tasktemplates[tasktemplate].get('statusSet'):
                if int(tasktemplates[tasktemplate]['statusSet']) == process:
                    if templates_count.get(process):
                        templates_count[process] += [tasktemplates[tasktemplate]['general']]
                    else:
                        templates_count[process] = [tasktemplates[tasktemplate]['general']]
    return templates_count

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

if __name__ == "__main__":
    limit_overflow = False
    request_count = 0
    processes_bpmn = {}

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
    # templates_count = count_templates()

    with open(os.path.join(PF_BACKUP_DIRECTORY, 'processes_bpmn.json'), 'r') as read_file:
        processes_loaded = json.load(read_file)
    for process in processes_loaded:
        processes_bpmn[int(process)] = processes_loaded[process]

    for process in processes_bpmn:
        if process == 230526:
            for tasktemplate in processes_bpmn[process]['threads']:
                nodes = set()
                vectors = set()
                reverse_vectors = set()
                reverse_nodes = set()
                used_reverse_nodes = set()
                all_vectors = set()
                vector_last_nodes = set()
                first_node = -1
                for thread in processes_bpmn[process]['threads'][tasktemplate]:
                    for i, node in enumerate(thread):
                        if not i and first_node < 0:
                            first_node = node
                        nodes.add('g' + str(node))
                        vectors.add('g' + str(thread[i]) + '-t' + str(node))
                        nodes.add('t' + str(node))
                        vectors.add('t' + str(thread[i]) + '-s' + str(node))
                        nodes.add('s' + str(node))
                        vectors.add('s' + str(thread[i]) + '-f' + str(node))
                        nodes.add('f' + str(node))
                        if i:
                            all_vectors.add(str(thread[i - 1]) + '-' + str(node))
                # Находим ноды с несколькими входящими векторами, в них всегда есть обратные петли
                for vector in all_vectors:
                    if int(vector.split('-')[1]) in vector_last_nodes:
                        reverse_nodes.add(int(vector.split('-')[1]))
                    vector_last_nodes.add(int(vector.split('-')[1]))
                # Генерируем векторы, разделяя на прямые и обратные
                for thread in processes_bpmn[process]['threads'][tasktemplate]:
                    for i, node in enumerate(thread):
                        if i:
                            has_reverse = False
                            v_name = 'f' + str(thread[i - 1]) + '-g' + str(node)
                            if node in used_reverse_nodes:
                                has_reverse = True
                            if node in reverse_nodes and node not in used_reverse_nodes:
                                used_reverse_nodes.add(node)
                            if thread[i] in thread[:i]:
                                has_reverse = True
                            if has_reverse and v_name not in vectors:
                                reverse_vectors.add(v_name)
                            if not has_reverse and v_name not in reverse_vectors:
                                vectors.add(v_name)
                # Сокращаем gateway в которых один входящий или по одному входящему и исходящему вектору
                gateway_nodes = []
                for node in nodes:
                    if node[0] in ['f', 'g']:
                        gateway_nodes.append(node)
                for node in gateway_nodes:
                    vectors_in = []
                    vectors_out = []
                    for vector in vectors:
                        if vector.find('-' + node) > -1:
                            vectors_in.append(vector)
                        elif vector.find(node + '-') > -1:
                            vectors_out.append(vector)
                    for vector in reverse_vectors:
                        if vector.find('-' + node) > -1:
                            vectors_in.append(vector)
                        elif vector.find(node + '-') > -1:
                            vectors_out.append(vector)
                    if len(vectors_in) > 0 and len(vectors_out) == 0:
                        # Преобразование gateway без выходов в финиш - замена (добавление и удаление нод и векторов)
                        nodes.remove(node)
                        nodes.add('e' + node[1:])
                        for vector in vectors_in:
                            if vector in vectors:
                                vectors.remove(vector)
                                vectors.add(vector.replace(node, 'e' + node[1:]))
                            elif vector in reverse_vectors:
                                reverse_vectors.remove(vector)
                                reverse_vectors.add(vector.replace(node, 'e' + node[1:]))
                            else:
                                print('АВАРИЯ!!!! Так быть не должно никогда!!!!')
                    elif len(vectors_in) == 1 and len(vectors_out) == 1:
                        # Сокращение gateway: удаляем gateway, добавляем вектор, заменяющий сокращаемые вектора
                        nodes.remove(node)
                        if vectors_in[0] in vectors and vectors_out[0] in vectors:
                            vectors.add(vectors_in[0].split('-')[0] + '-' + vectors_out[0].split('-')[1])
                        else:
                            reverse_vectors.add(vectors_in[0].split('-')[0] + '-' + vectors_out[0].split('-')[1])
                        # Удаляем векторы
                        vectors.discard(vectors_in[0])
                        vectors.discard(vectors_out[0])
                        reverse_vectors.discard(vectors_in[0])
                        reverse_vectors.discard(vectors_out[0])
                bpmn_graph_xml = diagram.BpmnDiagramGraph()
                bpmn_graph_xml.add_process_to_diagram('process_2')
                process_id = list(bpmn_graph_xml.process_elements.keys())[0]
                bpmn_graph_xml.diagram_attributes['id'] = 'diagr_pr' + str(process) + '_tmpl' + tasktemplate
                bpmn_graph_xml.diagram_attributes['name'] = \
                    'ПРОЦЕСС: ' + processes[process]['name'] + ' ШАБЛОН: ' + tasktemplates[int(tasktemplate)]['title']
                bpmn_graph_xml.plane_attributes['id'] = 'plane_pr' + str(process) + '_tmpl' + tasktemplate
                bpmn_graph_xml.plane_attributes['bpmnElement'] = process_id
                bpmn_graph_xml.process_elements[process_id]['id'] = process_id
                #off = """
                bpmn_graph_xml.add_start_event_to_diagram(process_id, 'Начало', node_id='start')
                #"""
                for node in nodes:
                    if node[0] == 'g':
                        bpmn_graph_xml.add_exclusive_gateway_to_diagram(process_id, '', node_id=node)
                    if node[0] == 'f':
                        bpmn_graph_xml.add_exclusive_gateway_to_diagram(process_id, '', node_id=node)
                    elif node[0] == 't':
                        bpmn_graph_xml.add_task_to_diagram(process_id, statuses[int(node[1:])]['name'], node_id=node)
                    elif node[0] == 's':
                        event_id, event = bpmn_graph_xml.add_flow_node_to_diagram(
                            process_id,
                            consts.Consts.intermediate_throw_event,
                            statuses[int(node[1:])]['name'],
                            node_id=node)
                        bpmn_graph_xml.diagram_graph.nodes[event_id][consts.Consts.event_definitions] = []
                    elif node[0] == 'e':
                        bpmn_graph_xml.add_end_event_to_diagram(process_id, '', node_id=node)
                for vector in vectors:
                    bpmn_graph_xml.add_sequence_flow_to_diagram(process_id, vector.split('-')[0], vector.split('-')[1],
                                                                '')
                bpmn_graph_xml.add_sequence_flow_to_diagram(process_id, 'start', 'g' + str(first_node),
                                                            'start-g' + str(first_node))
                bpmn_graph_xml.process_elements[process_id]['node_ids'] = list(bpmn_graph_xml.diagram_graph.nodes)
                layout.generate_layout(bpmn_graph_xml)
                for vector in reverse_vectors:
                    bpmn_graph_xml.add_sequence_flow_to_diagram(process_id, vector.split('-')[0], vector.split('-')[1],
                                                                '')
                
                bpmn_graph_xml.process_elements[process_id]['node_ids'] = list(bpmn_graph_xml.diagram_graph.nodes)
                bpmn_graph_xml.export_xml_file('./', 'pr' + str(process) + '_tmpl' + tasktemplate + '.bpmn')




    q=0






