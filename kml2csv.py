#!/usr/bin/python2.7
#
# kml2csv.py - Convert FR24 KML file to CSV
#
#
# Usage:
#
# shell$ ./kml2csv.py [options] filename
#
# Converts filename.kml to filename.csv
#
# Options:
#
# -d - add computed values for delta time, delta distance, rate of turn, vertical speed,
#      instantaneous vertical speed (default)
# -r - do not add computed values
# -s n - smooth computed values over last n sample, default is 10
#
# Copyright, License, etc
# -----------------------
#
# Feel free to use or modify this as you wish. A credit would be nice if you do anything
# interesting with it.
#

import xml.etree.ElementTree as ET
import sys
import os
import re
from math import *
from datetime import datetime, timedelta
from argparse import ArgumentParser

metres_to_feet = 3.28084
earth_circum = 360 * 60
earth_radius = earth_circum / (2 * pi)
default_samples = 10

class placemark(object) :

    fields = ( 'time', 'timestamp', 'latitude', 'longitude', 'altitude', 'heading', 'speed' )
    delta_fields = ( 'delta_t', 'delta_s', 'cspeed', 'rot', 'vspeed', 'inst_vspeed' )
    all_fields = fields + delta_fields
    field_formats = { 'delta_s' : '%.3f',
                      'cspeed' : '%.1f',
                      'rot' : '%.2f',
                      'vspeed' : '%.0f',
                      'inst_vspeed' : '%.0f',
                      'latitude' : '%.6f',
                      'longitude' : '%.6f',
                      }
    prevs = []

    def __init__(self, pm) :
        self.time = get_first(pm, 'when').text
        self.timestamp = to_unix_time(self.time)
        self.longitude, self.latitude, alt = tuple([ float(v) for v in get_first(pm, 'coordinates').text.split(',') ])
        self.altitude = int(float(alt) * 3.28084)
        self.heading = float(get_first(pm, 'heading').text)
        descr = get_first(pm, 'description').text
        speed = get_from_descr(descr, 'Speed')
        self.speed = float(re.search(r'(\d+)', speed).group(1))

    def do_delta(self, new_prev, samples) :
        self.delta_t = self.timestamp - new_prev.timestamp
        placemark.prevs.append(new_prev)
        try :
            prev = placemark.prevs[0]
        except IndexError :
            return
        if len(placemark.prevs) > samples :
            placemark.prevs = placemark.prevs[1:]
        delta_t = self.timestamp - prev.timestamp
        if delta_t > 2 :
            delta_lat, delta_long = self.latitude - prev.latitude, self.longitude - prev.longitude
            delta_altitude = self.altitude - prev.altitude
            delta_heading = self.heading - prev.heading
            if delta_heading > 180 :
                delta_heading -= 360
            elif delta_heading < -180 :
                delta_heading += 360
            if fabs(delta_heading) < 5 :
                self.rot = 0
            else :
                self.rot = delta_heading / delta_t
            self.vspeed = int(60 * delta_altitude / delta_t)
            self.inst_vspeed = int(60 * (self.altitude - new_prev.altitude) / self.delta_t)
            y = radians(delta_lat) * earth_radius
            x = radians(delta_long) * earth_radius * cos(radians(self.latitude))
            self.delta_s = sqrt(x*x + y*y) * (self.delta_t / delta_t)
            self.cspeed = 3600 * self.delta_s / float(self.delta_t)
            

    def __str__(self) :
        return ','.join([ self.to_str(f) for f in placemark.all_fields ])

    def to_str(self, field) :
        result = ''
        value = getattr(self, field, None)
        if value is not None :
            if isinstance(value, float) :
                fmt = placemark.field_formats.get(field, '%.0f')
                result = fmt % (value,)
            else :
                result = str(value)
        return result
            

    @staticmethod
    def tags(delta) :
        return ','.join(placemark.all_fields if delta else placemark.fields)
            

def get_named_element(elem, tag, name) :
    for e in elem.iter(xmlns+tag) :
        for child in e :
            if child.tag==xmlns+'name' and child.text==name :
                return e

def get_first(elem, tag) :
    for e in elem.iter(xmlns+tag) :
        return e
    return None

def get_from_descr(descr, label) :
    rx = r'<span><b>'+label+r':</b></span>.*?<span>(.*?)</span>'
    m = re.search(rx, descr)
    if m :
        return m.group(1)
    else :
        return None

def to_unix_time(t) :
    m = re.match(r'^(\d+)-(\d+)-(\d+)T(\d+):(\d+):(\d+).*$', t)
    if m :
        args = [int(n) for n in m.group(1,2,3,4,5,6)]
        dt = datetime(*args)
        return (dt - datetime(1970,1,1)).total_seconds()

def make_csv(outfile, root, args) :
    prev = None
    with open(outfile, 'w') as f :
        f.write(placemark.tags(args.delta)+'\n')
        for pm in root.iter(xmlns+'Placemark') :
            p = placemark(pm)
            if prev :
                p.do_delta(prev, args.sample)
            f.write(str(p)+'\n')
            prev = p

class parse_args(object) :

    def __init__(self) :
        p = ArgumentParser()
        p.add_argument('file')
        p.add_argument('-d', '--delta', default=True, action='store_true',
                     help='generate computed delta values')
        p.add_argument('-r', '--raw', action='store_false', dest='delta',
                     help='EXPLAIN the query instead of running it')
        p.add_argument('-s', '--sample', default=default_samples, type=int,
                     help='number of samples for smoothed values')
        self.args = p.parse_args()

def main() :
    global xmlns
    args = parse_args().args
    file = args.file
    if file.endswith('.kml') :
        infile = file
        outfile = file[:-4] + '.csv'
    else :
        infile = file + '.kml'
        outfile = file + '.csv'
    tree = ET.parse(infile)
    root = tree.getroot()
    xmlns = root.tag[:root.tag.find('}')+1]
    route = get_named_element(root, 'Folder', 'Route')
    make_csv(outfile, route, args)

main()
