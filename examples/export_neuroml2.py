import pkg_resources
from neuron import h
from pyneuroml.neuron import export_to_neuroml2, set_erev_for_mechanism

# export_to_neuroml2("test.hoc", "test.morphonly.cell.nml", includeBiophysicalProperties=False)
# export_to_neuroml2("test.hoc", "test.biophys.cell.nml", includeBiophysicalProperties=True)
# export_to_neuroml2("Cell_Scnn1a.hoc", "Cell_Scnn1a.cell.nml", known_rev_potentials={"na":60,"k":-90,"ca":140}, includeBiophysicalProperties=True)

# TODO Cell_Scnn1a.hoc contains erev potentials as `ek = -107`, `ehcn = -45` in its sections descriptions
# mview_neuroml2.hoc must use them. If it does not find a rev mechanism then it should print warning and continue!

resource_package = 'pyneuroml.neuron'
resource_path = '/mview_neuroml2.hoc'
template = pkg_resources.resource_filename(resource_package, resource_path)

h.load_file("stdrun.hoc")
h.load_file("import3d.hoc")
h.load_file("mview.hoc")
h.load_file(template)
h.load_file('Cell_Scnn1a.hoc')
cell_hoc = h.Cell_Scnn1a('.', 'Cell_Scnn1a.swc')

known_rev_potentials = {"na":60,"k":-90,"ca":140}
for ion in known_rev_potentials.keys():
    set_erev_for_mechanism(ion, known_rev_potentials[ion])

mv = h.ModelView(0)
mv_xml = h.ModelViewNeuroML2(mv)
export_filepath = 'Cell_Scnn1a.cell'
mv_xml.exportNeuroML2(export_filepath, 2, 0)
