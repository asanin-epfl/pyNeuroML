#!/usr/bin/env python
#
#   A script which can be run to generate a LEMS file to analyse the behaviour 
#   of channels in NeuroML 2
#

import sys
import os
import os.path
import argparse
import pprint
import glob
import re

import neuroml.loaders as loaders
from pyneuroml import pynml
import airspeed
import matplotlib.pyplot as plt

pp = pprint.PrettyPrinter(depth=4)

OUTPUT_DIR = os.getcwd()
TEMPLATE_FILE = "%s/LEMS_Test_TEMPLATE.xml" % (os.path.dirname(__file__))
HTML_TEMPLATE_FILE = "%s/ChannelInfo_TEMPLATE.html" % \
                        (os.path.dirname(__file__))
V = "rampCellPop0[0]/v" # Key for voltage trace in results dictionary.  
     
MAX_COLOUR = (255, 0, 0)
MIN_COLOUR = (255, 255, 0)

DEFAULTS = {'v': False,
            'minV': -100,
            'maxV': 100,
            'temperature': 6.3,
            'duration': 100,
            'clampDelay': 10,
            'clampDuration': 80,
            'clampBaseVoltage': -70,
            'stepTargetVoltage': 20,
            'erev': 0,
            'caConc': 5e-5,
            'ivCurve': False,
            'norun':False,
            'nogui':False,
            'html':False} 

def process_args():
    """ 
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
                description=("A script which can be run to generate a LEMS "
                             "file to analyse the behaviour of channels in "
                             "NeuroML 2"))

    parser.add_argument('channelFiles', 
                        type=str,
                        nargs='+',
                        metavar='<NeuroML 2 Channel file>', 
                        help="Name of the NeuroML 2 file(s)")
                        
                        
    parser.add_argument('-v',
                        action='store_true',
                        default=DEFAULTS['v'],
                        help="Verbose output")
                        
    parser.add_argument('-minV', 
                        type=int,
                        metavar='<min v>',
                        default=DEFAULTS['minV'],
                        help="Minimum voltage to test (integer, mV)")
                        
    parser.add_argument('-maxV', 
                        type=int,
                        metavar='<max v>',
                        default=DEFAULTS['maxV'],
                        help="Maximum voltage to test (integer, mV)")
                        
    parser.add_argument('-temperature', 
                        type=float,
                        metavar='<temperature>',
                        default=DEFAULTS['temperature'],
                        help="Temperature (float, celsius)")
                        
    parser.add_argument('-duration', 
                        type=float,
                        metavar='<duration>',
                        default=DEFAULTS['duration'],
                        help="Duration of simulation in ms")
                        
    parser.add_argument('-clampDelay', 
                        type=float,
                        metavar='<clamp delay>',
                        default=DEFAULTS['clampDelay'],
                        help="Delay before voltage clamp is activated in ms")
                        
    parser.add_argument('-clampDuration', 
                        type=float,
                        metavar='<clamp duration>',
                        default=DEFAULTS['clampDuration'],
                        help="Duration of voltage clamp in ms")
                        
    parser.add_argument('-clampBaseVoltage', 
                        type=float,
                        metavar='<clamp base voltage>',
                        default=DEFAULTS['clampBaseVoltage'],
                        help="Clamp base (starting/finishing) voltage in mV")
                        
    parser.add_argument('-stepTargetVoltage', 
                        type=float,
                        metavar='<step target voltage>',
                        default=DEFAULTS['stepTargetVoltage'],
                        help=("Voltage in mV through which to step voltage "
                              "clamps"))
                        
    parser.add_argument('-erev', 
                        type=float,
                        metavar='<reversal potential>',
                        default=DEFAULTS['erev'],
                        help="Reversal potential of channel for currents")
                        
    parser.add_argument('-caConc', 
                        type=float,
                        metavar='<Ca2+ concentration>',
                        default=DEFAULTS['caConc'],
                        help=("Internal concentration of Ca2+ (float, "
                              "concentration in mM)"))
                        
    parser.add_argument('-norun',
                        action='store_true',
                        default=DEFAULTS['norun'],
                        help=("If used, just generate the LEMS file, "
                              "don't run it"))
                        
    parser.add_argument('-nogui',
                        action='store_true',
                        default=DEFAULTS['nogui'],
                        help=("Supress plotting of variables and only save "
                              "data to file"))
                        
    parser.add_argument('-html',
                        action='store_true',
                        default=DEFAULTS['html'],
                        help=("Generate a HTML page (as well as a Markdown "
                              "version...) featuring the plots for the "
                              "channel"))
                        
    parser.add_argument('-ivCurve',
                        action='store_true',
                        default=False,
                        help=("Save currents through voltage clamp at each "
                              "level & plot current vs voltage for ion "
                              "channel"))
                        
                        
    return parser.parse_args()


def get_colour_hex(fract):
    rgb = [ hex(int(x + (y-x)*fract)) for x, y in zip(MIN_COLOUR, MAX_COLOUR) ]
    col = "#"
    for c in rgb: col+= ( c[2:4] if len(c)==4 else "00")
    return col

    
def get_state_color(s):
    col='#000000'
    if s.startswith('m'): col='#FF0000'
    if s.startswith('h'): col='#00FF00'
    if s.startswith('n'): col='#0000FF'
    if s.startswith('a'): col='#FF0000'
    if s.startswith('b'): col='#00FF00'
    if s.startswith('c'): col='#0000FF'
    if s.startswith('q'): col='#FF00FF'
    if s.startswith('e'): col='#00FFFF'
    if s.startswith('f'): col='#FFFF00'
    
    return col


def merge_with_template(model, templfile):
    if not os.path.isfile(templfile):
        templfile = os.path.join(os.path.dirname(sys.argv[0]), templfile)
    with open(templfile) as f:
        templ = airspeed.Template(f.read())
    return templ.merge(model)


def generate_lems_channel_analyser(channel_file, channel, min_target_voltage, 
                      step_target_voltage, max_target_voltage, clamp_delay, 
                      clamp_duration, clamp_base_voltage, duration, erev, 
                      gates, temperature, ca_conc, iv_curve):
                      
    target_voltages = []
    v = min_target_voltage
    while v <= max_target_voltage:
        target_voltages.append(v)
        v+=step_target_voltage

    target_voltages_map = []
    for t in target_voltages:
        fract = float(target_voltages.index(t)) / (len(target_voltages)-1)
        info = {}
        info["v"] = t
        info["v_str"] = str(t).replace("-", "min")
        info["col"] = get_colour_hex(fract)
        target_voltages_map.append(info)
        #print info

    model = {"channel_file":        channel_file, 
             "channel":             channel, 
             "target_voltages" :    target_voltages_map,
             "clamp_delay":         clamp_delay,
             "clamp_duration":      clamp_duration,
             "clamp_base_voltage":  clamp_base_voltage,
             "min_target_voltage":  min_target_voltage,
             "max_target_voltage":  max_target_voltage,
             "duration":  duration,
             "erev":  erev,
             "gates":  gates,
             "temperature":  temperature,
             "ca_conc":  ca_conc,
             "iv_curve":  iv_curve}
             
    #pp.pprint(model)

    merged = merge_with_template(model, TEMPLATE_FILE)

    return merged


def convert_case(name):
    """Converts from camelCase to under_score"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def process_channel_file(channel_file,a):
    ## Get name of channel mechanism to test
    if a.v: 
        print("Going to test channel from file: "+ channel_files)

    if not os.path.isfile(channel_file):
        raise IOError("File could not be found: %s!\n" % channel_file)
    
    doc = loaders.NeuroMLLoader.load(channel_file)

    channels = list(doc.ion_channel_hhs.__iter__()) + \
               list(doc.ion_channel.__iter__())

    channels_info = []
    for channel in channels:  
        setattr(channel,'file',channel_file)  
        if not hasattr(channel,'notes'):
            setattr(channel,'notes','')
    
        new_lems_file = make_lems_file(channel,a)
        if not a.norun:
            results = run_lems_file(new_lems_file,a)        

        if a.iv_curve:
            iv_data = compute_iv_curve(channel,a,results)
        else:
            iv_data = None

        if not a.nogui:
            plot_channel(channel,a,results,iv_data=iv_data)

        channel_info = {key:getattr(channel,key) \
                            for key in ['id','file','notes']}
        channels_info.append(channel_info)
    return channels_info


def get_channel_gates(channel):
    channel_gates = []
    for gates in ['gates','gate_hh_rates','gate_hh_tau_infs']:
        channel_gates += [g.id for g in getattr(channel,gates)]
    if not len(channel_gates):
        raise AttributeError("No gates found in a channel with ID %s" % \
                                channel.id)
    return channel_gates


def make_lems_file(channel,a):
    gates = get_channel_gates(channel)
    lems_content = generate_lems_channel_analyser(
        channel.file, channel.id, a.min_v, 
        a.step_target_voltage, a.max_v, a.clamp_delay, 
        a.clamp_duration, a.clamp_base_voltage, a.duration, 
        a.erev, gates, a.temperature, a.ca_conc, a.iv_curve)
    new_lems_file = os.path.join(OUTPUT_DIR,
                                 "LEMS_Test_%s.xml" % channel.id)
    lf = open(new_lems_file, 'w')
    lf.write(lems_content)
    lf.close()
    if a.v:
        print("Written generated LEMS file to %s\n" % new_lems_file)
    return new_lems_file


def run_lems_file(lems_file,a):
    results = pynml.run_lems_with_jneuroml(
                lems_file, nogui=True, 
                load_saved_data=True, plot=False, verbose=a.v)
    return results


def plot_channel(channel,a,results,iv_data=None,grid=True):
    plot_kinetics(channel,a,results,grid=grid)
    plot_steady_state(channel,a,results,grid=grid)
    if iv_data:
        plot_iv_curve(channel,a,iv_data)


def plot_kinetics(channel,a,results,grid=True):
    fig = plt.figure()
    fig.canvas.set_window_title(("Time Course(s) of activation variables of "
                                 "%s from %s at %s degC") 
                                 % (channel.id, channel.file, a.temperature))

    plt.xlabel('Membrane potential (V)')
    plt.ylabel('Time Course - tau (s)')
    plt.grid('on' if grid else 'off')
    
    gates = get_channel_gates(channel)
    for g in gates:
        g_tau = "rampCellPop0[0]/test/%s/%s/tau" \
                % (channel.id, g) # Key for conductance variable.  
        col = get_state_color(g)
        plt.plot(results[V], results[g_tau], color=col, 
                 linestyle='-', label="%s %s tau" % (channel.id, g))
        plt.gca().autoscale(enable=True, axis='x', tight=True)
        plt.legend()

        if a.html:
            save_fig('%s.tau.png' % channel.id)

def plot_steady_state(channel,a,results,grid=True):
    fig = plt.figure()
    fig.canvas.set_window_title(("Steady state(s) of activation variables of "
                                 "%s from %s at %s degC")
                                 % (channel.id, channel.file, a.temperature))
    plt.xlabel('Membrane potential (V)')
    plt.ylabel('Steady state - inf')
    plt.grid('on' if grid else 'off')
    
    gates = get_channel_gates(channel)
    for g in gates:
        g_inf = "rampCellPop0[0]/test/%s/%s/inf" \
                % (channel.id, g)
        col = get_state_color(g)
        plt.plot(results[V], results[g_inf], color=col, 
                 linestyle='-', label="%s %s inf" % (channel.id, g))
        plt.gca().autoscale(enable=True, axis='x', tight=True)
        plt.legend()

        if a.html:
            save_fig('%s.inf.png' % channel.id)


def save_fig(name):
    html_dir = make_html_dir()
    png_path = os.path.join(html_dir,name)
    plt.savefig(png_path)


def make_html_dir():
    html_dir = os.path.join(OUTPUT_DIR,'html')
    if not os.path.isdir(html_dir):
        os.makedirs(html_dir)
    return html_dir


def compute_iv_curve(channel,a,results,grid=True):                  
    # Based on work by Rayner Lucas here: 
    # https://github.com/openworm/
    # BlueBrainProjectShowcase/blob/master/
    # Channelpedia/iv_analyse.py              
    dat_path = os.path.join(OUTPUT_DIR,
                            '%s.i_*.lems.dat' % channel.id)
    file_names = glob.glob(dat_path)                        
    i_peaks = {}
    i_steady = {}
    hold_v = []
    currents = {}
        
    for file_name in file_names:
        name = os.path.split(file_name)[1] # Filename without path.    
        times = []
        v_match = re.match("%s.i_(.*)\.lems\.dat" \
                           % channel.id, name)
        voltage = v_match.group(1)
        voltage = voltage.replace("min", "-")
        voltage = float(voltage)/1000
        hold_v.append(voltage)
        
        currents[voltage] = []                
        i_file  = open(name)
        i_max = -1*sys.float_info.min
        i_min = sys.float_info.min
        i_steady[voltage] = None
        t_steady_end = (a.clamp_delay + \
                        a.clamp_duration)/1000.0
        for line in i_file:
            t = float(line.split()[0])
            times.append(t)
            i = float(line.split()[1])
            currents[voltage].append(i)
            if i>i_max: i_max = i
            if i<i_min: i_min = i
            if t < t_steady_end:
                i_steady[voltage] = i
            
        i_peak = i_max if abs(i_max) > abs(i_min)\
                       else i_min
        i_peaks[voltage] = -1 * i_peak

    hold_v.sort()
    
    iv_file = open('%s.i_peak.dat' % channel.id,'w')
    for v in hold_v:
        iv_file.write("%s\t%s\n" % (v,i_peaks[v]))
    iv_file.close()

    iv_file = open('%s.i_steady.dat' % channel.id,'w')
    for v in hold_v:
        iv_file.write("%s\t%s\n" % (v,i_steady[v]))
    iv_file.close()

    return hold_v, times, currents, i_peaks, i_steady
          

def plot_iv_curve(channel,a,iv_data,grid=True):
    hold_v, times, currents, i_peaks, i_steady = iv_data
    plot_iv_curve_vm(channel,a,hold_v,times,currents,grid=grid)
    plot_iv_curve_peak(channel,a,hold_v,i_peaks,grid=grid)
    plot_iv_curve_ss(channel,a,hold_v,i_steady,grid=grid)


def plot_iv_curve_vm(channel,a,hold_v,times,currents,grid=True):
    # Holding potentials           
    fig = plt.figure()
    fig.canvas.set_window_title(("Currents through voltage clamp for %s "
                                 "from %s at %s degC, erev: %s V") 
                                 % (channel.id, channel.file, 
                                    a.temperature, a.erev))
    plt.xlabel('Time (s)')
    plt.ylabel('Current (A)')
    plt.grid('on' if grid else 'off')
    for v in hold_v:
        col = get_colour_hex(
                float(hold_v.index(v))/len(hold_v))
        plt.plot(times, currents[v], color=col, 
                   linestyle='-', label="%s V" % v)
    plt.legend()


def plot_iv_curve_peak(channel,a,hold_v,i_peaks,grid=True):     
    # Peaks
    fig = plt.figure()
    fig.canvas.set_window_title(
        "Currents vs. holding potentials at erev = %s V"\
        % a.erev)
    plt.xlabel('Membrane potential (V)')
    plt.ylabel('Current (A)')
    plt.grid('on' if grid else 'off')
    plt.plot(hold_v, [i_peaks[v] for v in hold_v], 
               'ko-', label="Peak currents")
    plt.legend()
            

def plot_iv_curve_ss(channel,a,hold_v,i_steady,grid=True):     
    # Steady states
    fig = plt.figure()
    fig.canvas.set_window_title(
        "Currents vs. holding potentials at erev = %s V" \
        % a.erev)
    plt.xlabel('Membrane potential (V)')
    plt.ylabel('Current (A)')
    plt.grid('on' if grid else 'off')
    plt.plot(hold_v, [i_steady[v] for v in hold_v], 
               'ko-', label="Steady state currents")
    plt.legend()


def make_html_file(info):
    merged = merge_with_template(info, HTML_TEMPLATE_FILE)
    html_dir = make_html_dir()
    new_html_file = os.path.join(html_dir,'ChannelInfo.html')
    lf = open(new_html_file, 'w')
    lf.write(merged)
    lf.close()
    print('Written HTML info to: %s' % new_html_file)


def main(args=None):
    if args is None:
        args = process_args()
    run(a=args)


def run(a=None,**kwargs): 
    if a is None:
        a = argparse.Namespace()
    
    # Add arguments passed in by keyword.  
    for key,value in kwargs.items():
        setattr(a,key,value)

    # Add defaults for arguments not provided.  
    for key,value in DEFAULTS.items():
        if not hasattr(a,key):
            setattr(a,key,value)

    # Change all values to under_score from camelCase.  
    for key,value in a.__dict__.items():
        new_key = convert_case(key)
        if new_key != key:
            setattr(a,new_key,value)
            delattr(a,key)

    info = {'info': ("Channel information at: "
                     "T = %s degC, "
                     "E_rev = %s mV, "
                     "[Ca2+] = %s mM") % (a.temperature, a.erev, a.ca_conc),
            'channels': []}
                       
    for channel_file in a.channel_files:
        channel_info = process_channel_file(channel_file,a)
        info['channels'].append(channel_info)
    
    pp.pprint(info)                        
    if not a.nogui and not a.html:
        plt.show()
    elif a.html:
        make_html_file(info)


if __name__ == '__main__':
    main()
