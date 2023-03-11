# %%[markdown]
# Author: Nelson Liu
# 
# Email: [nliu@uncharted.software](mailto:nliu@uncharted.software)

# %%[markdown]
# Convert between a model's Petri net representation (ACSet) and its ODE representation (MathML)
#
# Source: [https://github.com/ml4ai/skema/pull/133](https://github.com/ml4ai/skema/pull/133)

# %%
import os
import json
import requests
from tqdm import tqdm
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib as mpl
import matplotlib.pyplot as plt
from typing import NoReturn, Optional, Any
import latex2mathml.converter

# %%
REST_URL_SKEMA = "https://skema-rs.staging.terarium.ai"

# %%
# Helper functions

# Convert LaTeX equations to MathML equations
def convert_latex2mathml(model_latex: Optional[list]) -> list:

    for i, m in enumerate(model_latex):
        m = latex2mathml.converter.convert(m)

        # Replace some unicode characters
        # SKEMA throws error otherwise
        m = m.replace('&#x0003D;', '=') 
        m = m.replace('&#x02212;', '-')
        m = m.replace('&#x0002B;', '+')

        model_latex[i] = m

    return model_latex

# Convert MathML equations to Petri-net ACSet
def convert_mathml2petri(model_mathml: Optional[list] = None) -> dict:

    model_petri = {}

    # SKEMA API health check
    if model_mathml == None:
        url = f'{REST_URL_SKEMA}/ping'
        res = requests.get(url)
        print(f'{res.url}: Code {res.status_code}\n\t\"{res.text}\"')

    # SKEMA API for MathML-to-ACSet conversion
    else:
        url = f'{REST_URL_SKEMA}/mathml/acset'
        res = requests.put(url, json = model_mathml)
        print(f'{res.url}: Code {res.status_code}\n\t\"{res.text}\"')
        if res.status_code == 200:
            model_petri = res.json()

    return model_petri

# Draw Petri net using NX
def draw_graph(model: dict, ax: Optional[Any] = None, node_type: Optional[list] = None, edge_type: Optional[list] = None, save_path: Optional[str] = None, legend: bool = True) -> NoReturn:

    # Build graph
    map_petrinet_names = {
        'S': {(i + 1): s['sname'] for i, s in enumerate(model['S'])}, 
        'T': {(j + 1): s['tname'] for j, s in enumerate(model['T'])}
    }

    df = pd.DataFrame({
        'source': [map_petrinet_names['S'][d['is']] for d in model['I']] + [map_petrinet_names['T'][d['ot']] for d in model['O']],
        'source_type': ['S' for d in model['I']] + ['T' for d in model['O']],
        'target': [map_petrinet_names['T'][d['it']] for d in model['I']] + [map_petrinet_names['S'][d['os']] for d in model['O']],
        'target_type': ['T' for d in model['I']] + ['S' for d in model['O']],
        'edge_type': ['I' for d in model['I']] + ['O' for d in model['O']]
    })

    G = nx.DiGraph()
    for i in ['source', 'target']:
        G.add_nodes_from([(node, {'type': node_type}) for __, (node, node_type) in df[[i, f"{i}_type"]].iterrows()])

    G.add_edges_from([(edge['source'], edge['target'], {'type': edge['edge_type']}) for __, edge in df.iterrows()])


    # Draw graph

    # Colors
    # node_colors = mpl.cm.Pastel1(plt.Normalize(0, 8)(range(8)))
    edge_colors = mpl.cm.tab10(plt.Normalize(0, 10)(range(10)))

    # Layout
    # pos = nx.kamada_kawai_layout(G)
    # pos = nx.spring_layout(G, k = 0.5)
    nlist = [
        [node[0] for node in G.nodes.data(True) if node[1]['type'] == 'S'], 
        [node[0] for node in G.nodes.data(True) if node[1]['type'] == 'T']
    ]
    pos = nx.shell_layout(G, nlist = nlist)


    if node_type == None:
        map_node_type = {x: i for i, x in enumerate(set([type(node[1]['type']) for node in G.nodes.data(True)]))}

        if len(map_node_type) == 1:
            map_node_type = {x: i for i, x in enumerate(set([node[1]['type'] for node in G.nodes.data(True)]))}
            node_type = [map_node_type[node[1]['type']] for node in G.nodes.data(True)]
        else:
            node_type = [map_node_type[type(node[1]['type'])] for node in G.nodes.data(True)]

    if edge_type == None:
        map_edge_type = {x: i for i, x in enumerate(set([edge[2]['type'] for edge in G.edges.data(True)]))}
        edge_type = [map_edge_type[edge[2]['type']] for edge in G.edges.data(True)]

    if ax == None:
        fig, ax = plt.subplots(1, 1, figsize = (8, 8))

    h = []

    for t, i in map_node_type.items():
        h.append(nx.draw_networkx_nodes(
            ax = ax, 
            G = G, 
            pos = pos,
            nodelist = [node for node, nt in zip(G.nodes, node_type) if nt == i],
            node_color = [i for node, nt in zip(G.nodes, node_type) if nt == i], 
            # node_size = i * 500 + 100,
            node_size = 100,
            cmap = mpl.cm.Pastel1, vmin = 0, vmax = 8,
            alpha = 0.8,
            label = t
        ))

    for t, i in map_edge_type.items():
        __ = nx.draw_networkx_edges(
            ax = ax,
            G = G,
            pos = pos,
            arrows = True,
            edgelist = [edge[:2] for edge in G.edges.data(True) if edge[2]['type'] == t], 
            label = t,
            edge_color = [i for edge in G.edges.data(True) if edge[2]['type'] == t],
            edge_cmap = mpl.cm.tab10,
            edge_vmin = 0, edge_vmax = 10,
            connectionstyle = 'arc3,rad=0.2'
        )

    __ = nx.draw_networkx_labels(
        ax = ax,
        G = G, 
        pos = pos,
        labels = {node: node for node in G.nodes},
        font_size = 8
    )

    M = np.max(np.nanmax(np.array(list(pos.values())), axis = 0))
    m = np.min(np.nanmin(np.array(list(pos.values())), axis = 0))
    m = 1.5 * max([np.abs(M), np.abs(m)])
    __ = plt.setp(ax, xlim = (-m, m), ylim = (-m, m))

    if legend == True:
        __ = ax.legend(handles = h + [mpl.patches.FancyArrow(0, 0, 0, 0, color = edge_colors[i, :], width = 1) for t, i in map_edge_type.items()], labels = list(map_node_type.keys()) + list(map_edge_type.keys()), loc = 'upper center', bbox_to_anchor = (0.5, -0.01), ncols = 4)

    if save_path != None:
        fig.savefig(save_path, dpi = 150)


# %%[markdown]
# ## Test with SIR Model

# %%
# Example in Petri net representation
models = {}

model_name = 'SIR'
models[model_name] = {}
models[model_name]['petri'] = {
    "S": [
        {"sname":"I", "uid":0},
        {"sname":"R", "uid":1},
        {"sname":"S", "uid":2}
    ],
    "T":[
        {"tname":"β"},
        {"tname":"γ"}
    ],
    "I":[
        {"it":1,"is":1},
        {"it":1,"is":3},
        {"it":2,"is":1}
    ],
    "O":[
        {"ot":1,"os":1},
        {"ot":1,"os":1},
        {"ot":2,"os":2}
    ]
}

# %%
# Example in ODE representation
models[model_name]['mathml'] = [
    "<math display=\"block\" style=\"display:inline-block;\"><mrow><mfrac><mrow><mi>d</mi><mi>S</mi></mrow><mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mo>−</mo><mi>β</mi><mi>S</mi><mi>I</mi></mrow></math>",
    "<math display=\"block\" style=\"display:inline-block;\"><mrow><mfrac><mrow><mi>d</mi><mi>I</mi></mrow><mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mi>β</mi><mi>S</mi><mi>I</mi><mo>−</mo><mi>γ</mi><mi>I</mi></mrow></math>",
    "<math display=\"block\" style=\"display:inline-block;\"><mrow><mfrac><mrow><mi>d</mi><mi>R</mi></mrow><mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mi>γ</mi><mi>I</mi></mrow></math>"
]

# %%
# SKEMA API health check
__ = convert_mathml2petri()

# %%
# Use SKEMA API for MathML-to-ACSet conversion
models[model_name]['mathml_petri'] = convert_mathml2petri(models[model_name]['mathml'])

# %%
# Plot both Petri net models
fig, axes = plt.subplots(1, 2, figsize = (8, 4))
fig.suptitle(model_name)
__ = plt.setp(axes[0], title = 'Ground Truth')
draw_graph(models[model_name]['petri'], ax = axes[0])

__ = plt.setp(axes[1], title = 'SKEMA Inference')
draw_graph(models[model_name]['mathml_petri'], ax = axes[1])

# %%[markdown]
# The two models - `model_petri` and `model_petri_math = skema_mathml2acset(model_mathml)` match up 
# mathematically.

# %%[markdown]
# ## Test with SIDARTHE model

# %%
# SIDARTHE equations in LaTeX
model_name = 'SIDARTHE'
models[model_name] = {}

models[model_name]['latex'] = [
    r"\frac{d S}{d t} = - \alpha S I - \beta S D - \gamma S A - \delta S R",
    r"\frac{d I}{d t} = \alpha S I + \beta S D + \gamma S A + \delta S R - \eta I - \zeta I - \lambda I",
    r"\frac{d D}{d t} = \epsilon I - \eta D - \rho D",
    r"\frac{d A}{d t} = \zeta I - \theta A - \mu A - \kappa A",
    r"\frac{d R}{d t} = \eta D + \theta A - \nu R - \xi R",
    r"\frac{d T}{d t} = \mu A + \nu R - \sigma T - \tau T",
    r"\frac{d H}{d t} = \lambda I + \rho D + \kappa A + \xi R + \sigma T",
    r"\frac{d E}{d t} = \tau T",
]

# %%
# Convert LaTeX equations to MathML equations
models[model_name]['mathml'] = convert_latex2mathml(models[model_name]['latex'])

# %%
# Convert MathML equations to Petri net (ACSset)
models[model_name]['mathml_petri'] = convert_mathml2petri(models[model_name]['mathml']) 

# %%[markdown]
# Note that one gets Code 502 error if the MathML string uses the unicode for `=, +, -`

# %%
fig, axes = plt.subplots(1, 2, figsize = (8, 4))
fig.suptitle('MathML-to-ACSet Conversion by SKEMA')
__ = plt.setp(axes[0], title = 'SIR')
draw_graph(models['SIR']['mathml_petri'], ax = axes[0])

__ = plt.setp(axes[1], title = 'SIDARTHE')
draw_graph(models['SIDARTHE']['mathml_petri'], ax = axes[1])


# %%[markdown]
# ## Test with an age-contact model

# %%
model_name = 'age_contact'
models[model_name] = {}
models[model_name]['latex'] = [
    r"\frac{d A_1}{dt} = - 2 a_{11} A_1 A_1 - 2 a_{11} A_1 A_1 + a_{11} A_1 A_1 + a_{11} A_1 A_1 + a_{12} A_1 A_2 - a_{12}A_1 A_2 - a_{21} A_2 A_1 + a_{21} A_2 A_1",
    r"\frac{d A_2}{dt} = - 2 a_{22} A_2 A_2 - 2 a_{22} A_2 A_2 + a_{22} A_2 A_2 + a_{22} A_2 A_2 + a_{12} A_1 A_2 - a_{12}A_1 A_2 - a_{21} A_2 A_1 + a_{21} A_2 A_1"
]

# %%
# Ground truth Petri net
# (generated using AlgebraicPetri)
models[model_name]['petri'] = {
    "T": [
        {"tname":"A1_A1"},
        {"tname":"A1_A2"},
        {"tname":"A2_A1"},
        {"tname":"A2_A2"}
    ],
    "S":[
        {"sname":"A1"},
        {"sname":"A2"}
    ],
    "I":[
        {"it":1,"is":1},
        {"it":1,"is":1},
        {"it":2,"is":1},
        {"it":2,"is":2},
        {"it":3,"is":2},
        {"it":3,"is":1},
        {"it":4,"is":2},
        {"it":4,"is":2}
    ],
    "O":[
        {"ot":1,"os":1},
        {"ot":1,"os":1},
        {"ot":2,"os":1},
        {"ot":2,"os":2},
        {"ot":3,"os":2},
        {"ot":3,"os":1},
        {"ot":4,"os":2},
        {"ot":4,"os":2}
    ]
}

# %%
# Convert LaTeX equations to MathML equations
models[model_name]['mathml'] = convert_latex2mathml(models[model_name]['latex'])

# Convert MathML equations to Petri net (ACSset)
models[model_name]['mathml_petri'] = convert_mathml2petri(models[model_name]['mathml']) 

# %%
fig, axes = plt.subplots(1, 2, figsize = (8, 4))
fig.suptitle('MathML-to-ACSet Conversion by SKEMA')

fig.suptitle('Age-Contact Model')
__ = plt.setp(axes[0], title = 'Ground Truth')
draw_graph(models[model_name]['petri'], ax = axes[0])

__ = plt.setp(axes[1], title = 'SKEMA Inference')
draw_graph(models[model_name]['mathml_petri'], ax = axes[1])

# %%[markdown]
# Note: Missing edges in age-contact model
#
# Need to verify correctness of the age-contact model equations.
# 
# Let's try to generate the equations from the ground-truth Petri net.