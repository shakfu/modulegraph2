from modulegraph2 import reportbuilder

b = reportbuilder.ReportBuilder('clean.dot', modules=['clean'], exclude_stdlib=True)
b.make_graph()
b.output_graph()
b.render_graph()