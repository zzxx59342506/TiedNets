__author__ = 'Agostino Sturaro'

import os
import json
import networkx as nx
import matplotlib.pyplot as plt

try:
    import Queue as Q  # ver. < 3.0
except ImportError:
    import queue as Q


def find_neighboring_subs(G, v):
    subs = list()
    q = Q.Queue()
    q.put(v)
    discovered = list()
    discovered.append(v)
    while not q.empty():
        u = q.get()
        # print('G.neighbors(u) = {}'.format(G.neighbors(u)))  # debug
        for w in G.neighbors(u):
            if w not in discovered:
                discovered.append(w)
                # print(G.node[w]['type'])
                if len(G.node[w]['sub_ids']) > 0:
                    subs.append(w)  # you reached a neighboring substation, don't search beyond it
                else:
                    q.put(w)  # keep searching
    # print('subs ' + str(subs))  #debug
    return subs


def add_generators(elec_gens_fpath, G):
    free_id = max(G.nodes()) + 1
    gen_names = list()
    gen_ids = list()
    gen_id_to_node = dict()  # only used for tests

    # map substation ids used in the map with node ids used in the graph
    sub_id_to_node = dict()
    for node in G.nodes():
        for sub_id in G.node[node]['sub_ids']:
            sub_id_to_node[sub_id] = node

    # here we assume there are no overlapping generators
    # add generators to the graph and connect them to their respective substations
    with open(elec_gens_fpath) as elec_gens_file:
        elec_gens = json.load(elec_gens_file)

        print('gen_cnt features = {}'.format(len(elec_gens['features'])))  # debug

        for gen in elec_gens['features']:
            gen_name = gen['properties']['NAME']  # these ids probably start from 1 and may not be continuous

            if gen['geometry'] is None:
                print('Missing geometry for generator {}'.format(gen_name))  # debug
                continue

            if gen_name in gen_names:
                print('Duplicated generator {}'.format(gen_name))  # debug
                continue

            gen_names.append(gen_name)  # remember this node id has been encountered
            gen_attrs = dict()
            gen_attrs['NAME'] = gen_name
            gen_attrs['COMPANY'] = gen['properties']['COMPANY']
            gen_attrs['MW'] = gen['properties']['MW']
            gen_attrs['SUBST_ID'] = gen['properties']['SUBST_ID']

            # remember coordinates as a tuple (lat, long)
            point = tuple(gen['geometry']['coordinates'])
            gen_attrs['x'] = point[0]
            gen_attrs['y'] = point[1]

            # add the node with the properties
            G.add_node(free_id, gen_attrs)
            gen_ids.append(free_id)
            gen_id_to_node[gen_name] = free_id
            free_id += 1

    print('len(gen_names) {}'.format(len(gen_names)))  # debug

    for gen_id in gen_ids:
        subs_to_link = G.node[gen_id]['SUBST_ID']
        subs_to_link = [node for node in subs_to_link.split(', ')]
        for sub_id in subs_to_link:
            node_id = sub_id_to_node[int(sub_id)]
            G.add_edge(gen_id, node_id)

    # small tests

    test_gen_node = gen_id_to_node['Minnesota Valley']
    test_neigh_nodes = list()
    test_neigh_nodes.append(sub_id_to_node[1090])
    print G.neighbors(test_gen_node) == test_neigh_nodes

    test_gen_node = gen_id_to_node['Rapids Energy Center']
    test_neigh_nodes = list()
    test_neigh_nodes.append(sub_id_to_node[878])
    test_neigh_nodes.append(sub_id_to_node[879])
    print G.neighbors(test_gen_node) == test_neigh_nodes

    return gen_ids

subs_G = nx.Graph()
final_G = nx.Graph()
subs = dict()
lines_by_id = dict()
point_to_id = dict()

elec_subs_fpath = os.path.normpath('datasets/ElecSubs_epsg_4326.geojson')
elec_lines_fpath = os.path.normpath('datasets/ElecLine_epsg_4326.geojson')
elec_gens_fpath = os.path.normpath('datasets/ElecGens_epsg_4326.geojson')
parsed_graph_fpath = os.path.normpath('MN_pow.graphml')
roles_fpath = os.path.normpath('MN_pow_roles.json')

this_dir = os.path.normpath(os.path.dirname(__file__))
os.chdir(this_dir)

if not os.path.isabs(elec_subs_fpath):
    elec_subs_fpath = os.path.abspath(elec_subs_fpath)
if not os.path.isabs(elec_lines_fpath):
    elec_lines_fpath = os.path.abspath(elec_lines_fpath)
if not os.path.isabs(elec_gens_fpath):
    elec_gens_fpath = os.path.abspath(elec_gens_fpath)
if not os.path.isabs(parsed_graph_fpath):
    parsed_graph_fpath = os.path.abspath(parsed_graph_fpath)

with open(elec_subs_fpath) as elec_subs_file:
    # elec_subs = json.load(elec_subs_file, parse_float=Decimal)
    elec_subs = json.load(elec_subs_file)

    print('sub_cnt features = {}'.format(len(elec_subs['features'])))  # debug

    # add nodes to a temporary graph
    for sub in elec_subs['features']:
        sub_id = sub['properties']['OBJECTID']  # these ids probably start from 1 and may not be continuous

        if sub['geometry'] is None:
            print('Missing geometry for substation {}'.format(sub_id))  # debug
            continue

        if sub_id in subs:
            print('Duplicated substation {}'.format(sub_id))  # debug
            continue

        sub_attrs = dict()
        sub_attrs['COMPANY'] = sub['properties']['COMPANY']
        sub_attrs['COMP_ID'] = sub['properties']['COMP_ID']
        sub_attrs['SUB_TYPE'] = sub['properties']['SUB_TYPE']

        # remember coordinates as a tuple (lat, long)
        point = tuple(sub['geometry']['coordinates'])
        sub_attrs['coordinates'] = point

        # store the properties of the substation, indexed by id
        subs[sub_id] = sub_attrs

        # remember that this substation is found at this point
        # there may be more than 1 substation in the same point

        if point not in point_to_id:
            point_id = len(point_to_id)
            point_to_id[point] = point_id
            subs_G.add_node(point_id, attr_dict={'x': point[0], 'y': point[1], 'sub_ids': list()})

        point_id = point_to_id[point]
        subs_G.node[point_id]['sub_ids'].append(sub_id)

    print('len(subs) {}'.format(len(subs)))  # debug

    for node in subs_G.nodes():
        if len(subs_G.node[node]['sub_ids']) > 1:
            print('Group of substations with the same coords ' + str(subs_G.node[node]['sub_ids']))

    final_G.add_nodes_from(subs_G.nodes(data=True))  # copy nodes representing substation locations to a multigraph

with open(elec_lines_fpath) as elec_lines_file:
    # elec_lines = json.load(elec_lines_file, parse_float=Decimal)
    voltages = list()
    elec_lines = json.load(elec_lines_file)
    for line in elec_lines['features']:
        line_id = line['properties']['OBJECTID']  # these ids probably start from 1 and may not be continuous

        if line['geometry'] is None:
            print('Missing geometry for line {}'.format(line_id))  # debug
            continue

        if line_id in lines_by_id:
            print('Duplicated line {}'.format(line_id))  # debug
            continue

        line_attrs = dict()
        line_attrs['COMPANY'] = line['properties']['COMPANY']
        line_attrs['COMP_ID'] = line['properties']['COMP_ID']
        line_attrs['ACDC'] = line['properties']['ACDC']

        voltage = line['properties']['VOLTAGE']
        line_attrs['VOLTAGE'] = voltage
        if voltage not in voltages:
            voltages.append(voltage)

        # remember the list of coordinates as a list of tuples (lat, long)
        line_attrs['points'] = list()
        for coords in line['geometry']['coordinates']:
            point = tuple(coords)
            line_attrs['points'].append(point)

        lines_by_id[line_id] = line_attrs

    print('len(lines) {}'.format(len(lines_by_id)))  # debug

for voltage in voltages:

    # make a graph consisting of the points that make up the electric lines

    temp_G = subs_G.copy()  # start by copying substation positions

    for line_id in lines_by_id:
        line_attrs = lines_by_id[line_id]

        if line_attrs['VOLTAGE'] != voltage:
            continue

        # remember that this line junction is found at this point
        # there may be more than 1 line junction in the same point

        for point in line_attrs['points']:

            if point not in point_to_id:
                point_id = len(point_to_id)
                point_to_id[point] = point_id
            else:
                point_id = point_to_id[point]

            if point_id not in temp_G.nodes():
                node_attrs = {'x': point[0], 'y': point[1], 'sub_ids': []}
                temp_G.add_node(point_id, attr_dict=node_attrs)

    # connect nodes that appear as consecutive points on the same transmission line

    for line_id in lines_by_id:
        line_attrs = lines_by_id[line_id]

        if line_attrs['VOLTAGE'] != voltage:
            continue

        # proceed linking consecutive points: 0 with 1, 1 with 2, etc.
        line_points = line_attrs['points']
        for idx in range(0, len(line_points)):
            if idx <= len(line_points) - 2:
                node = point_to_id[line_points[idx]]
                other_node = point_to_id[line_points[idx + 1]]
                if not temp_G.has_edge(node, other_node):
                    temp_G.add_edge(node, other_node, attr_dict={'line_ids': list()})
                temp_G.edge[node][other_node]['line_ids'].append(line_id)

    print('Consecutive line points linked')  # debug

    # add substation nodes to a new, simpler graph

    voltage_G = nx.Graph()
    sub_cnt = 0  # debug
    for node in temp_G.nodes():
        if len(temp_G.node[node]['sub_ids']) > 0:  # if this node is also a substation
            sub_cnt += 1  # debug
            voltage_G.add_node(node, attr_dict=dict(temp_G.node[node]))  # deep copy of the node attributes
            # print('G.node[node] = ' + str(G.node[node]))  # debug

    print('sub_cnt ' + str(sub_cnt))  # debug

    second_hits = 0
    for node in voltage_G.nodes():
        neighboring_subs = find_neighboring_subs(temp_G, node)  # search in the other graph
        for neighbor in neighboring_subs:
            if not voltage_G.has_edge(node, neighbor):
                voltage_G.add_edge(node, neighbor)  # TODO: think about some data for the edge (like voltage)
            else:
                second_hits += 1

    print('Voltage = {}, number of edges = {}'.format(voltage, voltage_G.number_of_edges()))  # debug

    # small test
    point_sub_24 = subs[24]['coordinates']
    node_sub_24 = point_to_id[point_sub_24]
    point_sub_1112 = subs[1112]['coordinates']
    node_sub_1112 = point_to_id[point_sub_1112]

    if node_sub_24 in voltage_G.neighbors(node_sub_1112):
        print('subs 24 and 1112 correctly connected')

    # another small test
    point_sub_93 = subs[93]['coordinates']
    node_sub_93 = point_to_id[point_sub_93]
    point_sub_105 = subs[105]['coordinates']
    node_sub_105 = point_to_id[point_sub_105]

    if node_sub_93 in voltage_G.neighbors(node_sub_105):
        print('subs 93 and 105 correctly connected')

    # copy graph edges (if they are already there, no problem)
    final_G.add_edges_from(voltage_G.edges())  # TODO: find a way to add edge data to a list

# add generators to the graph and save their node ids in the roles file

gen_ids = add_generators(elec_gens_fpath, final_G)
roles = {'generator': gen_ids}

with open(roles_fpath, 'w') as roles_file:
    json.dump(roles, roles_file)

# since GraphML does not support attributes with list values, we convert them to strings
for node in final_G.nodes():
    if 'sub_ids' in final_G.node[node]:
        final_G.node[node]['sub_ids'] = str(final_G.node[node]['sub_ids'])

# throw away isolated components (this step is optional)
components = sorted(nx.connected_components(final_G), key=len, reverse=True)
for component_idx in range(1, len(components)):
    print('isolated component {} = {}'.format(component_idx, components[component_idx]))
    final_G.remove_nodes_from(components[component_idx])
print('node count without isolated components = {}'.format(final_G.number_of_nodes()))

# export graph in GraphML format
nx.write_graphml(final_G, parsed_graph_fpath)

# draw the final graph

pos = dict()
first_it = True
for node in final_G.nodes():
    x = final_G.node[node]['x']
    y = final_G.node[node]['y']
    pos[node] = [x, y]

    if first_it is True:
        x_min = x
        y_min = y
        x_max = x
        y_max = y
        first_it = False
    else:
        if x > x_max:
            x_max = x
        elif x < x_min:
            x_min = x
        if y > y_max:
            y_max = y
        elif y < y_min:
            y_min = y

margin = 0.2
delta_x = abs(x_max - x_min)
delta_y = abs(y_max - y_min)

print('x_min = {}\nx_max = {}\ny_min = {}\ny_max = {}'.format(x_min, x_max, y_min, y_max))
# plt.xlim(x_min - margin * delta_x, x_max + margin * delta_x)
# plt.xlim(y_min - margin * delta_y, y_max + margin * delta_y)
nx.draw_networkx(final_G, pos, with_labels=False, node_color='r', node_size=8, linewidths=0.0)

# debug
# generators no longer in the graph (probably because part of isolated components)
removed_gens = list()
remaining_nodes = final_G.nodes()
for gen_node in gen_ids:
    if gen_node not in remaining_nodes:
        removed_gens.append(gen_node)
        gen_ids.remove(gen_node)
        print('removed generator node {}'.format(gen_node))

nx.draw_networkx_nodes(final_G, pos, nodelist=gen_ids, node_color='b', node_size=8, linewidths=0.0)
plt.show()
plt.close()
