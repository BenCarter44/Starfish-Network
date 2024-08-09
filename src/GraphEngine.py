from multiprocessing import Pool
import random
from typing import Optional
from typing_extensions import Self
import networkx as nx  # type: ignore
from collections import deque


def display_graph(graph: nx.Graph):
    """Display graph to screen.

    Args:
        graph (NetworkX Graph Object): Graph to display
    """
    import gravis as gv  # type: ignore

    # Create a graph from a stored example

    # It comes with an edge property named "weight" which can be used as edge size
    fig = gv.vis(graph, use_edge_size_normalization=True)
    fig.display()


def map_val(
    x,
    in_min: int | float,
    in_max: int | float,
    out_min: int | float,
    out_max: int | float,
) -> float:
    """Linear interpolation of value from one range to another.

    Args:
        x (int | float): _description_
        in_min (int | float): _description_
        in_max (int | float): _description_
        out_min (int | float): _description_
        out_max (int | float): _description_

    Returns:
        float: Interpolated value
    """
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def assign_properties(g: nx.Graph):
    """Assign colors and styling for graph before drawing

    Args:
        g (NetworkX Graph Object): Graph Object
    """
    # Node properties: Size by centrality, shape by size, color by community
    colors = [
        "red",
        "blue",
        "green",
        "orange",
        "pink",
        "brown",
        "yellow",
        "cyan",
        "magenta",
        "violet",
    ]
    max_val = 0
    min_val = 100000
    for node_id in g.nodes:
        l = len(list(g.edges(node_id)))
        if l > max_val:
            max_val = l
        elif l < min_val:
            min_val = l

    for node_id in g.nodes:
        l = len(list(g.edges(node_id)))
        node = g.nodes[node_id]
        if 0.75 < map_val(l, min_val, max_val, 0, 1):
            node["color"] = "green"
        elif 0.50 < map_val(l, min_val, max_val, 0, 1):
            node["color"] = "yellow"
        elif 0.30 < map_val(l, min_val, max_val, 0, 1):
            node["color"] = "brown"
        else:
            node["color"] = "blue"

        node["size"] = map_val(l, min_val, max_val, 3, 6)
        node["num_edge"] = l

    # how many shortest paths pass through edge
    # edge_centralities = nx.edge_betweenness_centrality(g)
    # for edge_id in g.edges:
    #     edge = g.edges[edge_id]
    #     s = math.log2(map_val(edge_centralities[edge_id], 0, 1, 2, 1024)) / 10
    #     edge["size"] = edge_centralities[edge_id] / 20000
    #     edge["hover"] = edge_centralities[edge_id]

    g.graph["arrow_size"] = 0.5


def recommend_random_path(
    graph: nx.Graph, source: int, target: int, cutoff=5
) -> list[int]:
    """Recursive entry for random path generation.

    Use auto_cutoff_recommend_random_path() for automatically determining cutoff value

    Args:
        graph (nx.Graph): Graph to search
        source (int): Source Node ID
        target (int): Target Node ID
        cutoff (int, optional): Number of hops before cutoff. Defaults to 5.

    Returns:
        list[int]: List of node IDs in order to traverse
    """
    cutoff = cutoff - 1
    f = nx.has_path(graph, source, target)
    if not (f):
        return []

    # print(f"{source} -> {target}")
    f = nx.shortest_path_length(graph, source, target) + 1
    if f > cutoff:
        return []

    # Equivalent to this, however rather than finding all paths first,
    # it picks a random edge traversing the graph.
    #
    # pths = nx.all_simple_paths(graph, source, target, cutoff=cutoff)
    # out = random.choice(list(pths))

    out: list[int] = []
    out_d: deque[int] = deque()

    visits_route = nx.DiGraph()
    visits_route.add_nodes_from(list(graph.nodes))
    visits_depth = nx.DiGraph()
    visits_depth.add_nodes_from(list(graph.nodes))

    r = recommend_paths_v3(
        graph,
        source,
        target,
        output_stack=out_d,
        cutoff=cutoff,
        visit_route=visits_route,
        visit_depth=visits_depth,
    )
    count = 0
    while r[0] != 1:
        out_d.clear()
        r = recommend_paths_v3(
            graph,
            source,
            target,
            output_stack=out_d,
            cutoff=cutoff,
            visit_route=visits_route,
            visit_depth=visits_depth,
        )
        # has path! (from has_path) above.
        if r[0] != 1:
            count += 1
        else:
            count = 0
        if count > 20 + cutoff:
            out = []
            out_d = deque()

            visits_route = nx.DiGraph()
            visits_route.add_nodes_from(list(graph.nodes))
            visits_depth = nx.DiGraph()
            visits_depth.add_nodes_from(list(graph.nodes))
            count = 0
        # input()

    # recommend_paths_v2(graph, source, target, output_stack=out_d, cutoff=cutoff)
    out = list(out_d)
    # Check if path actually is a path!
    assert nx.is_path(graph, out)
    return out


def pick_random_child(
    graph: nx.Graph, node: int, exclude: Optional[list[int]] = None
) -> int | None:
    """Pick a random child of a node.

    Args:
        graph (nx.Graph): Graph
        node (int): Parent node
        exclude (int, optional): Exclude node IDs. Defaults to None.

    Returns:
        int: Node ID of selected child. OR returns None if no child available.
    """
    if exclude is None:
        exclude = list()

    output: set[int] = set()

    neighbors = set(nx.neighbors(graph, node))

    for n in neighbors:
        output.add(n)

    output.difference_update(exclude)

    if len(output) == 0:
        return None

    r = random.choice(list(output))
    return r


def recommend_paths_v3(
    graph: nx.Graph,
    source: int,
    target: int,
    depth: int = 0,
    output_stack: deque[int] = deque(),
    visit_depth: nx.DiGraph = nx.DiGraph(),
    visit_route: nx.DiGraph = nx.DiGraph(),
    cutoff: int = 10,
):
    """A random searching algorithm that is somewhat Breadth First and Depth First.

    Use recommend_random_path() or auto_cutoff_recommend_random_path() as entry point.

    The algorithm first picks a random child of the source node, and continues picking until
    either reaching the target or hitting the cutoff. It will not go back to any node
    it has traveled to in the current circuit. It like "casts a line" like in fishing.

    If hitting the cutoff, it will try again restarting at the source node; however,
    it will keep track of the node that "errored out" and not visit it again. (preventing
    it from doing the same route again)

    Args:
        graph (nx.Graph): Graph to search
        source (int): Source Node ID
        target (int): Target Node ID
        depth (int, optional): Counter of the current depth the recursion is at. Defaults to 0.
        output_stack (deque[int], optional): The "trail" that the algorithm is on. Defaults to empty deque().
        visit_depth (nx.DiGraph, optional): A graph of depth "errored-out" nodes. Persistent! Defaults to empty nx.DiGraph().
        visit_route (nx.DiGraph, optional): A graph of route-length "errored-out" nodes. Persistent! Defaults to nx.DiGraph().
        cutoff (int, optional): A cutoff of nodes before erroring-out. Defaults to 10.

    Returns:
        int: 0 for Depth Limit, 1 for Found, 2 for Dead End
        int: Node ID of run
        int: Recursive Flag

    Return data is merely for the recursion. Actual usable data is available on the output_stack variable.

    """
    # This will be BFS rather than DFS as in v2.
    # When node reports back depth error or no route, go back to top instead of parents.
    #  Visits: remove all visits except the one bringing the error!

    # print(f"{' ' * depth}{depth} Source {source} {target}")
    output_stack.append(source)

    if source == target:
        # print(f"{' ' * depth}Success.")
        return (1, source, 1)  # success!

    if depth > cutoff:
        # print(f"{' ' * depth}Fail. Depth Exceeded")
        output_stack.pop()
        return (0, source, 1)  # fail! Dead End!

    visits = list(visit_route.successors(source))  # see if any
    # print(f"{' ' * depth}{depth} Route: {visits}")
    visits = visits + list(output_stack)
    # if depth == cutoff:
    #     visits += list(nx.neighbors(visit_depth, source))
    #     print(f"{' ' * depth}Do depth values")
    # else:
    # print(f"{' ' * depth}Ignore depth values")

    # print(f"{' ' * depth}{depth} Visits: {visits}")
    child = pick_random_child(graph, source, visits)
    if child == None:
        # print(f"{' ' * depth}Fail. No Route")
        output_stack.pop()
        return (2, source, 1)  # fail! Dead End!

    query = recommend_paths_v3(
        graph,
        child,  # type: ignore
        target,
        depth + 1,
        output_stack=output_stack,
        cutoff=cutoff,
        visit_depth=visit_depth,
        visit_route=visit_route,
    )
    # print(f"{' ' * depth}Recv")
    if query[0] == 1:
        return (query[0], query[1], 0)
    elif query[0] == 0:
        if query[2] == 1:
            visit_depth.add_edge(source, query[1])
        # query # depth limit.
        if target in nx.neighbors(graph, source):
            # try that one instead.
            return recommend_paths_v3(
                graph,
                target,
                target,
                depth + 1,
                output_stack=output_stack,
                cutoff=cutoff,
                visit_depth=visit_depth,
                visit_route=visit_route,
            )
        else:
            # delete all in visits EXCEPT hold.
            # visits.intersection_update(visit_depth)

            # print(
            #     f"{' ' * depth}Fail NR, Delete {list(visit_route.edges)} {list(visit_depth.edges)}."
            # )
            output_stack.pop()
            return (0, source, 0)
    else:
        if query[2] == 1:
            visit_route.add_edge(source, query[1])
        # delete all in visits EXCEPT hold.
        # visits.intersection_update(hold)
        # print(f"{' ' * depth}Fail NR.")
        return (query[0], query[1], 0)


def recommend_paths_v2(
    graph: nx.Graph,
    source: int,
    target: int,
    depth: int = 0,
    output_stack: deque[int] = deque(),
    visits: set[int] = set(),
    cutoff: int = 10,
):
    """A random searching algorithm that is mostly Depth First.

    An old algorithm. Superseded by recommend_paths_v3().

    The algorithm first picks a random child of the source node, and continues picking until
    either reaching the target or hitting the cutoff. It will not go back to any node
    it has traveled to in the current circuit. It like "casts a line" like in fishing.

    If hitting the cutoff, it will **go back only one step** and try again. It will keep
    going back in a DFS way until found.

    This algorithm is much slower and prone to dead ends / missing the node.
    (More likely you got the wrong path at the beginning than the end)

    Args:
        graph (nx.Graph): Graph to search
        source (int): Source Node ID
        target (int): Target Node ID
        depth (int, optional): Counter of the current depth the recursion is at. Defaults to 0.
        output_stack (deque[int], optional): The "trail" that the algorithm is on. Defaults to empty deque().
        visits: (set[int], optional): The nodes already visited. Defaults to empty set
        cutoff (int, optional): A cutoff of nodes before erroring-out. Defaults to 10.

    Returns:
        int: 0 for Depth Limit, 1 for Found, 2 for Dead End
        int: Node ID of run
        int: Recursive Flag

    Return data is merely for the recursion. Actual usable data is available on the output_stack variable.

    """
    # pick random neighbor.
    # follow the neighbor.
    # if either layer > depth or source = target, end!
    # Keep track of visited nodes and don't go back.

    # print(f"{' ' * depth}{depth} Source {source} {target} {print_tmp}")
    output_stack.append(source)
    visits.add(source)

    if depth > cutoff:
        # print(f"{' ' * depth}Fail. Depth Exceeded")
        output_stack.pop()
        return (0, source)  # fail! Dead End!

    if source == target:
        # print(f"{' ' * depth}Success.")
        return (1, source)  # success!

    child = pick_random_child(graph, source, visits)  # type: ignore
    if child == None:
        # print(f"{' ' * depth}Fail. No Route")
        output_stack.pop()
        return (2, source)  # fail! Dead End!

    hold = set()
    query = recommend_paths_v2(
        graph,
        child,  # type: ignore
        target,
        depth + 1,
        output_stack=output_stack,
        visits=visits,
        cutoff=cutoff,
    )
    visits.add(query[1])
    hold.add(query[1])
    while query[0] != 1:
        # pick a different child
        child = pick_random_child(graph, source, visits)  # type: ignore
        if child == None:
            # print(f"{' ' * depth}Fail. No Route")
            # pop ones visited.
            visits.difference_update(hold)
            # print(f"{' ' * depth}Delete: {hold}")
            output_stack.pop()
            return (2, source)  # fail! Dead End!
        query = recommend_paths_v2(
            graph,
            child,  # type: ignore
            target,
            depth + 1,
            output_stack=output_stack,
            visits=visits,
            cutoff=cutoff,
        )
        visits.add(query[1])
        hold.add(query[1])
        # input()
    return (1, source)


def auto_cutoff_recommend_random_path(
    graph: nx.Graph, source: int, target: int, max_hop_count: int
) -> list[int]:
    """Full Featured entry for random path generation.

    Args:
        graph (nx.Graph): Graph to search
        source (int): Source Node ID
        target (int): Target Node ID
        max_hop_count (int, optional): Number of hops before cutoff. Defaults to 5.

    Returns:
        list[int]: List of node IDs in order to traverse
    """
    path: list[int] = []
    cutoff = 1
    first_time = False
    while len(path) == 0:
        if cutoff > max_hop_count:
            break
        # print(f"Exe: {cutoff}")
        try:
            r = recommend_random_path(graph, source, target, cutoff=cutoff)
        except nx.exception.NodeNotFound:
            r = []
        if r == []:
            cutoff += 1
            first_time = True
            continue
        path = r
        if first_time:
            cutoff += 1
        else:
            break

    return path
