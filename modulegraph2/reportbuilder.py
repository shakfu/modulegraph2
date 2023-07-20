"""
ReportBuilder interface
"""
import os
import functools
import sys
from typing import Dict, Iterator, List, Sequence, Set, TextIO, Tuple, Union

from ._depinfo import DependencyInfo
from ._dotbuilder import export_to_dot
from ._htmlbuilder import export_to_html
from ._modulegraph import ModuleGraph
from ._nodes import BaseNode
from ._utilities import saved_sys_path, stdlib_module_names

# --- Helper code for the report builder

# Mapping from node class name to Graphviz attributes for the
# node.

NODE_ATTR = {
    "Script": {"shape": "note"},
    "Package": {"shape": "folder"},
    "SourceModule": {"shape": "rectangle"},
    "BytecodeModule": {"shape": "rectangle"},
    "ExtensionModule": {"shape": "parallelogram"},
    "BuiltinModule": {"shape": "hexagon"},
    "MissingModule": {"shape": "rectangle", "color": "red"},
}


def format_node(node: BaseNode, mg: ModuleGraph) -> Dict[str, Union[str, int]]:
    """
    Return a dict of Graphviz attributes for *node*

    Args:
       node: The node to format
       mg: The graph containing the node

    Returns:
       Graphviz attributes for the node
    """
    results: Dict[str, Union[str, int]] = {}
    if node in mg.roots():
        results["penwidth"] = 2
        results["root"] = "true"

    results.update(NODE_ATTR.get(type(node).__name__, {}))

    return results


def format_edge(
    source: BaseNode, target: BaseNode, edge: Set[DependencyInfo]
) -> Dict[str, Union[str, int]]:
    """
    Return a dict of Graphviz attributes for an edge

    Args:
      source: Source node for the edge
      target: Target node for the edge
      edge: Set of edge attributes

    Returns:
       Graphviz attributes for the edge
    """
    results: Dict[str, Union[str, int]] = {}

    if all(e.is_optional for e in edge):
        results["style"] = "dashed"

    if source.identifier.startswith(target.identifier + "."):
        results["weight"] = 10
        results["arrowhead"] = "none"

    return results


def group_nodes(graph: ModuleGraph) -> Iterator[Tuple[str, str, Sequence[BaseNode]]]:
    """
    Detect groups of reachable nodes in the graph.

    This function groups nodes in two ways:
    - Group all nodes related to a particular distribution
    - Group all nodes in the same stdlib package

    Args:
      graph: The dependency graph

    Returns:
      A list of ``(groupname, shape, nodes)`` for the
      groupings.
    """
    clusters: Dict[str, Tuple[str, str, List[BaseNode]]] = {}
    for node in graph.iter_graph():
        if not isinstance(node, BaseNode):
            continue

        if node.distribution is not None:
            dist = node.distribution.name
            if dist not in clusters:
                clusters[dist] = (dist, "tab", [])

            clusters[dist][-1].append(node)

    return iter(clusters.values())


class ReportBuilder:
    def __init__(
        self,
        output_file,
        output_format="dot",
        modules=None,
        scripts=None,
        distributions=None,
        excludes=None,
        paths=None,
        exclude_stdlib=False,
    ):
        self.output_file = output_file
        self.output_format = output_format
        self.modules = modules or []
        self.scripts = scripts or []
        self.distributions = distributions or []
        self.excludes = excludes or []
        self.paths = paths or []
        self.exclude_stdlib = exclude_stdlib
        if self.exclude_stdlib:
            self.excludes.extend(stdlib_module_names())

        self.mg = None  # ModuleGraph

    def make_graph(self):
        """
        Build a dependency graph.
        """
        with saved_sys_path():  # pragma: no branch
            for p in self.paths[::-1]:
                sys.path.insert(0, p)

            self.mg = ModuleGraph()
            self.mg.add_excludes(self.excludes)

            for name in self.modules:
                self.mg.add_module(name)
            for name in self.scripts:
                self.mg.add_script(name)
            for name in self.distributions:
                self.mg.add_distribution(name)

    def print_graph(self, file: TextIO):
        """
        Output the graph in the given output format to a text stream.

        Args:
          file: The text stream to data should be written to

          output_format: The format to use
        """
        if self.output_format == 'html':
            export_to_html(file, self.mg)

        elif self.output_format == 'dot':
            export_to_dot(
                file,
                self.mg,
                functools.partial(format_node, mg=self.mg),
                format_edge,
                group_nodes,
            )

        else:  # pragma: nocover
            raise AssertionError("Invalid OutputFormat")

    def output_graph(self):
        """
        Output the graph as specified.
        """
        if self.output_file is None:
            self.print_graph(sys.stdout, self.output_format, self.mg)
        else:
            try:
                with open(self.output_file, "w") as fp:  # pragma: no branch
                    self.print_graph(fp)

            except OSError as exc:
                print(exc, file=sys.stderr)
                raise SystemExit(1) from exc

    def render_graph(self, layout='dot', format='pdf'):
        """
        Render dot graph to using a layout engine and a specified format
        """
        assert format in ['html', 'ps', 'pdf', 'png', 'gif', 'jpg', 'json', 'svg']
        if self.output_format == 'dot' and self.output_file:
            render_file = os.path.splitext(self.output_file)[0] + '.' + format
            os.system(f'{layout} -T{format} -o {render_file} {self.output_file}')

