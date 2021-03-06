#!/usr/bin/env python2
""" The Eagle XML Format Parser """

# upconvert.py - A universal hardware design file format converter using
# Format:       upverter.com/resources/open-json-format/
# Development:  github.com/upverter/schematic-file-converter
#
# Copyright 2011 Upverter, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict

from upconvert.core.design import Design
from upconvert.core.components import Component, Symbol, Body
from upconvert.core.component_instance import ComponentInstance, SymbolAttribute
from upconvert.core.shape import Line

from upconvert.parser.eaglexml.generated import parse


class EagleXML(object):
    """ The Eagle XML Format Parser.

    This parser uses code generated by generateDS.py which converts an xsd
    file to a set of python objects with parse and export functions.
    That code is in generated.py. It was created by the following steps:

      1. Started with eagle.dtd from Eagle 6.2.0.
      2. Removed inline comments in dtd (was breaking conversion to xsd).
         The dtd is also stored in this directory.
      3. Converted to eagle.xsd using dtd2xsd.pl from w3c.
         The xsd is also stored in this directory.
      4. Run a modified version of generateDS.py with the following arguments:
           --silence --external-encoding=utf-8 -o generated.py
     """

    MULT = 90 / 25.4 # mm to 90 dpi

    def __init__(self):
        self.design = Design()

        # map components to gate names to symbol indices
        self.cpt2gate2symbol_index = defaultdict(dict)


    @staticmethod
    def auto_detect(filename):
        """ Return our confidence that the given file is an
        eagle xml schematic """

        with open(filename, 'r') as f:
            data = f.read(4096)
        confidence = 0.0
        if 'eagle.dtd' in data:
            confidence += 0.9
        return confidence


    def parse(self, filename):
        """ Parse an Eagle XML file into a design """

        root = parse(filename)

        self.make_components(root)
        self.make_component_instances(root)

        return self.design


    def make_components(self, root):
        """ Construct openjson components for an eagle model. """

        for lib in get_subattr(root, 'drawing.schematic.libraries.library', ()):
            for deviceset in get_subattr(lib, 'devicesets.deviceset', ()):
                cpt = self.make_component(lib, deviceset)
                self.design.components.add_component(cpt.name, cpt)


    def make_component(self, lib, deviceset):
        """ Construct an openjson component for a deviceset in a library. """

        cpt = Component(lib.name + ':' + deviceset.name)

        for gate in get_subattr(deviceset, 'gates.gate'):
            symbol = Symbol()
            cpt.add_symbol(symbol)
            self.cpt2gate2symbol_index[cpt][gate.name] = len(cpt.symbols) - 1
            symbol.add_body(self.make_body_from_symbol(lib, gate.symbol))

        return cpt


    def make_body_from_symbol(self, lib, symbol_name):
        """ Contruct an openjson Body from an eagle symbol in a library. """

        body = Body()

        symbol = [s for s in get_subattr(lib, 'symbols.symbol')
                  if s.name == symbol_name][0]

        for wire in symbol.wire:
            body.add_shape(Line((self.make_length(wire.x1),
                                 self.make_length(wire.y1)),
                                (self.make_length(wire.x2),
                                 self.make_length(wire.y2))))

        return body


    def make_component_instances(self, root):
        """ Construct openjson component instances for an eagle model. """

        parts = dict((p.name, p) for p
                     in get_subattr(root, 'drawing.schematic.parts.part', ()))

        for sheet in get_subattr(root, 'drawing.schematic.sheets.sheet', ()):
            for instance in get_subattr(sheet, 'instances.instance', ()):
                inst = self.make_component_instance(parts, instance)
                self.design.add_component_instance(inst)


    def make_component_instance(self, parts, instance):
        """ Construct an openjson component instance for an eagle instance. """

        part = parts[instance.part]

        library_id = part.library + ':' + part.deviceset

        # TODO pick correct symbol index
        inst = ComponentInstance(instance.part, library_id, 0)

        # TODO handle mirror
        # TODO handle smashed?
        attr = SymbolAttribute(self.make_length(instance.x),
                               self.make_length(instance.y),
                               self.make_angle(instance.rot or '0'))

        inst.add_symbol_attribute(attr)

        return inst


    def make_length(self, value):
        """ Make an openjson length measurement from an eagle length. """

        return int(round(float(value) * self.MULT))


    def make_angle(self, value):
        """ Make an openjson angle measurement from an eagle angle. """

        return float(value.lstrip('MSR')) / 180


def get_subattr(obj, name, default=None):
    """ Return an attribute given a dotted name, or the default if
    there is not attribute or the attribute is None. """

    for attr in name.split('.'):
        obj = getattr(obj, attr, None)

    return default if obj is None else obj
