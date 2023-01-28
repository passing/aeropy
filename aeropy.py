#!/usr/bin/python3

import argparse
import math
import re
import io
import png
from subprocess import Popen, PIPE


resolution = 100
debug = False


def error(message):
    print(f'ERROR: {message}')
    raise ValueError


class Labels():
    def __init__(self, labels_files=[]):
        self.labels = {}
        for labels_file in labels_files:
            self.import_file(labels_file)

    def import_file(self, labels_file):
        print(f'importing labels from \'{labels_file}\'')
        with open(labels_file) as f:
            self._import(f)

    def _import(self, file_object):
        lines = list(line.rstrip() for line in file_object.readlines())

        re_audacity = re.compile('^([0-9]+\.[0-9]+)\t([0-9]+\.[0-9]+)\t(.*)$')
        re_markers_minsec = re.compile('^M[0-9]+,([^,]*),([0-9]+):([0-9]{2}\.[0-9]{3})$')
        re_markers_seconds = re.compile('^M[0-9]+,([^,]*),([0-9]+\.[0-9]{3})$')
        re_markers_bb = re.compile('^M[0-9]+,([^,]*),([0-9]+)\.([0-9]{1})\.([0-9]{2})$')

        # audacity
        if all(re_audacity.search(line) for line in lines):
            for line in lines:
                m = re_audacity.search(line)
                start = float(m.group(1))
                end = float(m.group(2))
                name = m.group(3)
                self.labels[name] = [start, end]

        # markers
        elif lines[0] == '#,Name,Start':
            # minutes:seconds
            if all(re_markers_minsec.search(line) for line in lines[1:]):
                for line in lines[1:]:
                    m = re_markers_minsec.search(line)
                    name = m.group(1)
                    start = int(m.group(2)) * 60 + float(m.group(3))
                    end = start
                    self.labels[name] = [start, end]
            # seconds
            elif all(re_markers_seconds.search(line) for line in lines[1:]):
                for line in lines[1:]:
                    m = re_markers_seconds.search(line)
                    name = m.group(1)
                    start = float(m.group(2))
                    end = start
                    self.labels[name] = [start, end]
            # beats-bars (120 bpm)
            elif all(re_markers_bb.search(line) for line in lines[1:]):
                for line in lines[1:]:
                    m = re_markers_bb.search(line)
                    name = m.group(1)
                    start = (int(m.group(2)) - 1) * 2 + (int(m.group(3)) - 1) * 0.5 + int(m.group(4)) * 0.005
                    end = start
                    self.labels[name] = [start, end]
            else:
                error('markers file parse error')

        else:
            error('labels file format not known')

    def export_file(self, labels_file, labels_format='audacity'):
        with open(labels_file, 'w') as f:
            if labels_format == 'audacity':
                for (name, (start, end)) in self.labels.items():
                    f.write("{:.6f}\t{:.6f}\t{}\n".format(start, end, name))
            elif labels_format == 'markers':
                f.write('#,Name,Start\n')
                i = 1
                for (name, (start, end)) in self.labels.items():
                    f.write("M{},{},{:.0f}:{:06.3f}\n".format(i, name, *divmod(start, 60)))
                    i += 1
            else:
                error(f'unknown format {labels_format}')

    def label_start(self, name):
        if name in self.labels:
            return int(self.labels[name][0] * resolution)
        error(f'no such label \'{name}\'')

    def label_end(self, name):
        if name in self.labels:
            return int(self.labels[name][1] * resolution)
        error(f'no such label \'{name}\'')


class Color():
    amplify_table = list(int(math.sqrt(i / 255) * 255) for i in range(256))

    def __init__(self, red=0, green=0, blue=0):
        self.red = red
        self.green = green
        self.blue = blue

    def __repr__(self):
        return "Color({}, {}, {})".format(self.red, self.green, self.blue)

    def __add__(self, other):
        return Color(self.red + other.red, self.green + other.green, self.blue + other.blue)

    def __sub__(self, other):
        return Color(self.red - other.red, self.green - other.green, self.blue - other.blue)

    def __mul__(self, other):
        return Color(self.red * other, self.green * other, self.blue * other)

    def __round__(self):
        return Color(round(self.red), round(self.green), round(self.blue))

    def __abs__(self):
        return Color(abs(self.red), abs(self.green), abs(self.blue))

    def __eq__(self, other):
        return (self.red == other.red and self.green == other.green and self.blue == other.blue)

    def __or__(self, other):
        return Color(
            self.red if self.red is not None else other.red,
            self.green if self.green is not None else other.green,
            self.blue if self.blue is not None else other.blue
        )

    def distance(self, other):
        return round(math.sqrt(pow(self.red - other.red, 2) + pow(self.green - other.green, 2) + pow(self.blue - other.blue, 2)), 4)

    def get_rgb(self, amplify=False):
        if amplify:
            return (self.amplify_table[self.red], self.amplify_table[self.green], self.amplify_table[self.blue])
        else:
            return (self.red, self.green, self.blue)


class ColorList(list):
    def get_rgb(self, amplify=False):
        return list(c.get_rgb(amplify) for c in self)


class Arguments():
    def __init__(self, objects, name=None):
        self.objects = objects
        self.name = name

    def __hash__(self):
        return hash(tuple(self._expand()))

    def __eq__(self, other):
        return self._expand() == other._expand()

    def __str__(self):
        if self.name is not None:
            return self.name
        return ", ".join(map(str, self.objects))

    def _expand(self):
        values = []
        for o in self.objects:
            if isinstance(o, Arguments):
                values.extend(o._expand())
            elif isinstance(o, list):
                values.extend(o)
            else:
                values.append(o)
        return values

    def __len__(self):
        return len(self._expand())

    def __getitem__(self, key):
        return self._expand()[key]

    def __setitem__(self, key, value):
        self.objects[key] = value


class LightCommand:
    name = None
    command_variants = None
    valid_arguments = ((),)

    def __init__(self, arguments=[], noop=None):
        self.arguments = arguments
        self.noop = noop
        self._check_arguments()

    def _check_arguments(self):
        if not any(
            len(self.arguments) == len(self.valid_arguments[n]) and
            all(
                isinstance(self.arguments[m], self.valid_arguments[n][m])
                for m in range(len(self.valid_arguments[n]))
            )
            for n in range(len(self.valid_arguments))
        ):
            error(f'{self.name} has invalid arguments: ({self.arguments})')

    def __repr__(self):
        return f'{self.name} ({self.arguments})'

    def __hash__(self):
        return hash((self.name, self.arguments))

    def __eq__(self, other):
        return type(self) == type(other) and self.arguments == other.arguments

    def get_duration(self, root=None):
        return 0

    def __str__(self):
        return self.export()

    def _get_command_variant(self, command_variants, syntax):
        for s in syntax:
            if s in command_variants.keys():
                return command_variants[s]
        return command_variants['default']

    def _format_line(self, command_variants, syntax, arguments, noop):
        if command_variants:
            line = self._get_command_variant(command_variants, syntax)
            if arguments is not None:
                if 'legacy' in syntax:
                    line += f', {str(arguments)}'
                else:
                    line += f' ({str(arguments)})'
            if noop:
                line += noop
            return [line]
        return []

    def _export(self, indent, syntax):
        return self._format_line(self.command_variants, syntax, self.arguments, self.noop)

    def export(self, indent=0, syntax=[]):
        return "\n".join(self._export(indent, syntax))

    def _render_connected(self, color_pre, root):
        return [], color_pre

    def render(self, color_pre=Color(), root=None):
        return ColorList(self._render_connected(color_pre, root)[0])

    def resolve_constants(self):
        if isinstance(self.arguments, Arguments):
            self.arguments = Arguments(self.arguments._expand())

    def _resolve_unsupported(self):
        return [self]

    def strip(self):
        self.noop = None

    def compress(self, options):
        pass

    def add_namespace(self, namespace):
        pass


class LightCommandTime(LightCommand):
    name = 'time'
    command_variants = {'legacy': 'T', 'default': 'time'}
    valid_arguments = ((str, int), (str, str, str), (str, str, int), (str, int, int), (str, str, str, int), (str, str, int, int), (str, int, int, int))

    def resolve(self, labels, time, time_ref):
        objects = []

        time_target_delta = 0

        if isinstance(self.arguments[1], int):
            time_target = self.arguments[1]
        elif self.arguments[1] == 'label':
            time_target = labels.label_start(str(self.arguments[2]))
            if len(self.arguments) == 4:
                time_target_delta = self.arguments[3]
        else:
            error(f'cannot resolve "{self.name} ({self.arguments})"')

        if self.arguments[0] == 'set':
            time_add = time_ref + time_target + time_target_delta - time

            if (time_add > 0):
                if debug:
                    print(f'{self.name} ({self.arguments}): {time} / {time_ref}+{time_target}{time_target_delta:+}, add: {time_add}')
                objects.append(LightCommandNoop(noop=f'; TIME SHIFT ({self.arguments}): time={time}, target={time_ref}+{time_target}{time_target_delta:+}, add={time_add}'))
                objects.append(LightCommandDelay(arguments=Arguments([time_add])))
            elif (time_add < 0):
                error(f'target time in the past: time={time}, ref={time_ref}, target={time_target}{time_target_delta:+}, add={time_add} ({self.arguments})')

        elif self.arguments[0] == 'setref':
            objects.append(LightCommandNoop(noop=f'; TIME REFERENCE ({self.arguments}): old={time_ref}, new={time_target}{time_target_delta:+}'))
            time_ref = time_target + time_target_delta

        else:
            error(f'cannot resolve "{self.name} ({self.arguments})"')

        return (objects, time_ref)


class LightCommandDefine(LightCommand):
    name = 'define'
    command_variants = {'default': '#define'}
    valid_arguments = ((int,), (int, int), (int, int, int), (int, int, int, int))

    def _export(self, indent=0, syntax=[]):
        return [f'#define {self.arguments.name} {", ".join(map(str, self.arguments.objects))}']

    def add_namespace(self, namespace):
        self.arguments.name = namespace + self.arguments.name


class LightCommandNoop(LightCommand):
    name = 'noop'
    command_variants = {'default': 'noop'}

    def _export(self, indent=0, syntax=[]):
        if self.noop is not None:
            return [self.noop]
        return []


class LightCommandDelay(LightCommand):
    name = 'delay'
    command_variants = {'legacy': 'D', 'default': 'delay'}
    valid_arguments = ((int,),)
    max_duration = 65535

    def get_duration(self, root=None):
        return self.arguments[0]

    def _render_connected(self, color_pre, root=None):
        colors = []
        for n in range(self.get_duration()):
            colors.append(color_pre)
        return colors, color_pre

    def _resolve_unsupported(self):
        d = self.get_duration()
        if d > 0 and d <= self.max_duration:
            return [self]
        else:
            noop = f'; DELAY RESOLVE: {self.get_duration()}' + (self.noop or '')
            commands = [LightCommandNoop(noop=noop)]
            while d > 0:
                commands.append(LightCommandDelay(arguments=Arguments([min(d, self.max_duration)])))
                d -= self.max_duration
            return commands


class LightCommandColor(LightCommand):
    name = 'color'
    command_variants = {'legacy': 'C', 'default': 'color', 'british': 'colour'}
    valid_arguments = ((int, int, int),)

    def _color(self):
        return Color(self.arguments[0], self.arguments[1], self.arguments[2])

    def _render_connected(self, color_pre, root=None):
        return [], self._color() | color_pre


class LightCommandColorRed(LightCommandColor):
    name = 'red'
    command_variants = {'legacy': 'R', 'default': 'color.red', 'british': 'colour.red'}
    valid_arguments = ((int,),)

    def _color(self):
        return Color(self.arguments[0], None, None)


class LightCommandColorGreen(LightCommandColor):
    name = 'green'
    command_variants = {'legacy': 'G', 'default': 'color.green', 'british': 'colour.green'}
    valid_arguments = ((int,),)

    def _color(self):
        return Color(None, self.arguments[0], None)


class LightCommandColorBlue(LightCommandColor):
    name = 'blue'
    command_variants = {'legacy': 'B', 'default': 'color.blue', 'british': 'colour.blue'}
    valid_arguments = ((int,),)

    def _color(self):
        return Color(None, None, self.arguments[0])


class LightCommandRamp(LightCommandColor):
    name = 'ramp'
    command_variants = {'legacy': 'RAMP', 'default': 'ramp'}
    valid_arguments = ((int, int, int, int),)
    max_duration = 65535

    def get_duration(self, root=None):
        return self.arguments[3]

    def _render_connected(self, color_pre, root=None):
        color = self._color()
        duration = self.get_duration()
        colors = []
        for n in range(duration):
            colors.append(round(color_pre * (1 - (n / duration)) + color * (n / duration)))
        return colors, color

    def _resolve_unsupported(self):
        d = self.get_duration()
        if d == 0:
            return [LightCommandColor(arguments=Arguments(list(self._color().get_rgb())), noop=(self.noop or '') + ' ; RESOLVED')]
        elif d <= self.max_duration:
            return [self]
        else:
            error(f'resolving {self.name} with duration {d} (max = {self.max_duration}) not implemented')


class LightCommandSub(LightCommand):
    name = 'sub'
    command_variants = {'legacy': 'SUB', 'default': 'sub', 'call': 'call'}
    valid_arguments = ((str,),)

    def get_duration(self, root=None):
        if root is None:
            error('no root')
        return root.get_sub(self.arguments[0]).get_duration(root)

    def _render_connected(self, color_pre, root=None):
        if root is None:
            error('no root')
        return root.get_sub(self.arguments[0])._render_connected(color_pre, root)

    def add_namespace(self, namespace):
        self.arguments[0] = namespace + self.arguments[0]


class LightSequence(list, LightCommand):
    command_variants = {}
    command_variants_end = {}
    valid_arguments = ((),)
    valid_objects = ()
    level_add = 0

    def __init__(self, arguments=[], objects=[], noop=None):
        self._check_objects(objects)
        list.__init__(self, objects)
        LightCommand.__init__(self, arguments=arguments, noop=noop)

    def __hash__(self):
        return hash(tuple([LightCommand.__hash__(self)] + list(map(hash, self))))

    def append(self, item):
        self._check_object(item)
        list.append(self, item)

    def extend(self, items):
        self._check_objects(items)
        list.extend(self, items)

    def insert(self, index, item):
        self._check_object(item)
        list.insert(self, index, item)

    def valid_objects_dict(self):
        command_dict = {}
        for o in self.valid_objects:
            for c in o.command_variants.values():
                command_dict[c] = o
        return command_dict

    def exit_commands(self):
        return self.command_variants_end.values()

    def _check_object(self, item):
        if not isinstance(item, self.valid_objects):
            error(f'object \'{object.name}\' not allowed in \'{self.name}\'')

    def _check_objects(self, items):
        for item in items:
            self._check_object(item)

    def get_duration(self, root=None):
        return sum(object.get_duration(root) for object in self)

    def _export(self, indent=0, syntax=[]):
        lines = super()._export(indent, syntax)
        for o in self:
            lines.extend((" " * indent * self.level_add) + line for line in o._export(indent, syntax))
        lines.extend(self._format_line(self.command_variants_end, syntax, None, None))
        return lines

    def _render_connected(self, color_pre, root=None):
        colors = []
        for o in self:
            o_colors, color_pre = o._render_connected(color_pre, root)
            colors.extend(o_colors)
        return colors, color_pre

    def resolve_constants(self):
        LightCommand.resolve_constants(self)
        for index in range(len(self)):
            if isinstance(self[index], LightCommandDefine):
                self[index] = LightCommandNoop(noop=";" + self[index].export())
            else:
                self[index].resolve_constants()

    def _resolve_unsupported(self):
        self.resolve_unsupported()
        return [self]

    def resolve_unsupported(self):
        index = 0
        while index < len(self):
            resolved = self.pop(index)._resolve_unsupported()
            for r in resolved:
                self.insert(index, r)
                index += 1

    def add_namespace(self, namespace):
        super().add_namespace(namespace)
        for o in self:
            o.add_namespace(namespace)

    def strip(self):
        for o in self:
            o.strip()

        index = 0
        while index < len(self):
            if isinstance(self[index], LightCommandNoop):
                self.pop(index)
            else:
                index += 1

    def compress(self, options):
        for o in self:
            o.compress(options)

        old_len = len(self)
        self._compress_adjacent_delays()
        if old_len != len(self):
            print(f'compressed adjacent delays (old length: {old_len}, new length: {len(self)})')

        if len(self) > 2 and isinstance(self[0], (LightCommandColor, LightCommandRamp)) and all(isinstance(o, (LightCommandDelay, LightCommandColor, LightCommandRamp)) for o in self[1:]):
            self._convert_to_ramps()
            old_len = len(self)
            self._compress_douglas_peucker(0, len(self) - 1, options['epsilon'])
            if old_len != len(self):
                print(f'compressed ramp sequence (old length: {old_len}, new length: {len(self)}, epsilon: {options["epsilon"]})')
            self._convert_from_ramps()

        if len(self) > 2 and all(isinstance(o, (LightCommandDelay, LightCommandColor, LightCommandRamp, LightCommandSub)) for o in self):
            old_len = len(self)
            self._compress_repeat(options['root'])
            if old_len != len(self):
                print(f'compressed repetitions (old length: {old_len}, new length: {len(self)})')

    def _compress_adjacent_delays(self):
        index = 0
        while index < len(self):
            if isinstance(self[index], LightCommandDelay):
                c = 1
                while index + c < len(self) and isinstance(self[index + c], (LightCommandDelay, LightCommandNoop)):
                    if isinstance(self[index + c], LightCommandDelay):
                        arguments = Arguments([self[index].get_duration() + self[index + c].get_duration()])
                        noop = (self[index].noop or '') + (self[index + c].noop or '')
                        self[index + c] = LightCommandDelay(arguments=arguments, noop=noop)
                        self.pop(index)
                        index += c - 1
                        c = 1
                    else:
                        c += 1
            index += 1

    def _find_repeated_ngrams(self, objects):
        ngrams = {}

        # keep track of positions for searching
        pos_search = list(range(len(objects)))

        # store all ngrams and their occurences in dictionary
        for length in range(2, len(objects) // 2 + 1):
            if len(pos_search) > 0:
                n = 0
                while n < len(pos_search):
                    pos = pos_search[n]
                    if pos + length <= len(objects):
                        ngram = tuple(objects[pos: pos + length])
                        try:
                            ngrams[ngram].append(pos)
                        except KeyError:
                            ngrams[ngram] = [pos]
                        n += 1
                    else:
                        pos_search.pop(n)

                # exclude positions that got no duplicates so far
                n = 0
                while n < len(pos_search):
                    pos = pos_search[n]
                    ngram = tuple(objects[pos: pos + length])
                    if len(ngrams[ngram]) < 2:
                        pos_search.pop(n)
                    else:
                        n += 1

        # remove overlaps
        for ngram, n_positions in ngrams.items():
            c = 1
            while c < len(n_positions):
                if n_positions[c] - n_positions[c - 1] < len(ngram):
                    n_positions.pop(c)
                else:
                    c += 1

        # remove single occurences
        ngrams = dict(filter(lambda elem: len(elem[1]) > 1, ngrams.items()))

        return ngrams

    def _find_repeated_ngrams_grouped(self, objects):
        repeated_ngrams_grouped = {}

        for ngram, positions in self._find_repeated_ngrams(objects).items():
            repeated_ngrams_grouped[ngram] = []
            for p in range(len(positions)):
                if p > 0 and positions[p] - positions[p - 1] == len(ngram):
                    repeated_ngrams_grouped[ngram][-1].append(positions[p])
                else:
                    repeated_ngrams_grouped[ngram].append([positions[p]])

        return repeated_ngrams_grouped

    def _compress_repeat(self, root):
        while True:
            repeated_ngrams_grouped = self._find_repeated_ngrams_grouped(list(map(hash, self)))

            max_delta = 0
            ngram_hash = None
            ngram_positions_groups = []

            for n_hash, n_positions_groups in repeated_ngrams_grouped.items():

                command_decrease = len(n_hash) * sum(len(group) for group in n_positions_groups)
                # increase for defsub:
                command_increase = len(n_hash) + 1
                for group in n_positions_groups:
                    if len(group) > 1:
                        # increase for loop + sub
                        command_increase += 2
                    else:
                        # increase for sub
                        command_increase += 1

                delta = command_decrease - command_increase

                if delta > max_delta:
                    max_delta = delta
                    ngram_hash = n_hash
                    ngram_positions_groups = n_positions_groups

            # create and use subsequence
            if ngram_hash:
                ngram_length = len(ngram_hash)
                ngram = self[ngram_positions_groups[0][0]: ngram_positions_groups[0][0] + ngram_length]
                positions_total = sum(len(group) for group in ngram_positions_groups)

                if debug:
                    print(f'create subsequence for {positions_total} ({len(ngram_positions_groups)} groups) times repetition (delta = {max_delta}) of: {ngram}')

                arguments = Arguments([f's{hash(ngram_hash) % 1000000:06}'])
                sub = LightCommandSub(arguments=arguments, noop='; COMPRESSED')
                ds = LightSequenceDefsub(arguments=arguments, objects=ngram, noop='; COMPRESSED ({})'.format(positions_total))
                root.append(ds)

                pos_adjust = 0
                for group in ngram_positions_groups:
                    # remove objects
                    for p in range(len(group) * ngram_length):
                        self.pop(group[0] + pos_adjust)
                    # insert sub
                    if len(group) > 1:
                        loop = LightSequenceLoop(arguments=Arguments([len(group)]), objects=[sub], noop='; COMPRESSED')
                        self.insert(group[0] + pos_adjust, loop)
                    else:
                        self.insert(group[0] + pos_adjust, sub)
                    # adjust position
                    pos_adjust += 1 - (len(group) * ngram_length)

            else:
                return

    def _convert_to_ramps(self):
        color_pre = None
        index = 0
        while index < len(self):
            if isinstance(self[index], LightCommandRamp):
                color_pre = self[index]._color()
            elif isinstance(self[index], LightCommandColor):
                if color_pre is not None:
                    self[index] = LightCommandRamp(arguments=Arguments(list(self[index]._color().get_rgb()) + [0]), noop=self[index].noop)
                color_pre = self[index]._color()
            elif isinstance(self[index], LightCommandDelay):
                delay_duration = self[index].get_duration()
                if delay_duration > 0:
                    if color_pre is not None:
                        # delay followed by color
                        if index + 1 < len(self) and isinstance(self[index + 1], LightCommandColor) and not isinstance(self[index + 1], LightCommandRamp):
                            color = self[index + 1]._color()
                            if delay_duration > 1:
                                self[index] = LightCommandRamp(arguments=Arguments(list(color_pre.get_rgb()) + [delay_duration - 1]), noop=self[index].noop)
                                index += 1
                            else:
                                self.pop(index)
                            self[index] = LightCommandRamp(arguments=Arguments(list(color.get_rgb()) + [1]), noop=self[index].noop)
                            color_pre = color
                        else:
                            self[index] = LightCommandRamp(arguments=Arguments(list(color_pre.get_rgb()) + [delay_duration]), noop=self[index].noop)
                else:
                    self.pop(index)
                    index -= 1
            else:
                color_pre = None
            index += 1

    def _convert_from_ramps(self):
        color_pre = None
        index = 0
        while index < len(self):
            if isinstance(self[index], LightCommandRamp):
                color = self[index]._color()
                duration = self[index].get_duration()
                if color_pre is not None and color == color_pre:
                    self[index] = LightCommandDelay(arguments=Arguments([duration]), noop=self[index].noop)
                elif duration == 0:
                    self[index] = LightCommandColor(arguments=Arguments(list(color.get_rgb())), noop=self[index].noop)
                elif duration == 1:
                    self[index] = LightCommandDelay(arguments=Arguments([duration]))
                    self.insert(index + 1, LightCommandColor(arguments=Arguments(list(color.get_rgb())), noop=self[index].noop))
                    index += 1
                color_pre = color
            elif isinstance(self[index], LightCommandColor):
                color_pre = self[index]._color()
            elif isinstance(self[index], LightCommandDelay):
                pass
            else:
                color_pre = None
            index += 1

        self._compress_adjacent_delays()

    def _compress_douglas_peucker(self, pos_first, pos_last, epsilon):
        c_first = self[pos_first]._color()
        c_last = self[pos_last]._color()

        duration = sum(o.get_duration() for o in self[pos_first + 1: pos_last + 1])
        time = 0
        d_max = 0
        pos_max = 0

        if epsilon >= 0 and pos_last - pos_first >= 2:
            for i in range(pos_first + 1, pos_last):
                time += self[i].get_duration()
                c_interpolated = (c_first * (1 - (time / duration)) + c_last * (time / duration))
                c_diff = c_interpolated.distance(self[i]._color())
                if c_diff > d_max:
                    d_max = c_diff
                    pos_max = i

            if d_max <= epsilon:
                arguments = Arguments(self[pos_last].arguments._expand()[0: 3] + [duration])
                for i in range(pos_first, pos_last):
                    self.pop(pos_first + 1)
                self.insert(pos_first + 1, LightCommandRamp(arguments=arguments, noop=" ; COMPRESSED (e_max={:.2f})".format(d_max)))
            else:
                # start with last part as list indexes could otherwise be wrong
                self._compress_douglas_peucker(pos_max, pos_last, epsilon)
                self._compress_douglas_peucker(pos_first, pos_max, epsilon)


class LightSequenceLoop(LightSequence):
    name = 'loop'
    command_variants = {'legacy': 'L', 'default': 'loop'}
    command_variants_end = {'legacy': 'E', 'default': 'endloop', 'camel': 'endLoop'}
    valid_arguments = ((int,),)
    level_add = 1
    max_count = 255

    def _count(self):
        return self.arguments[0]

    def get_duration(self, root=None):
        return super().get_duration(root) * self._count()

    def _render_connected(self, color_pre, root=None):
        colors = []
        for l in range(self._count()):
            l_colors, color_pre = super()._render_connected(color_pre, root)
            colors.extend(l_colors)
        return colors, color_pre

    def _calculate_factors(self, number, max_number):
        m = max_number
        while m > 2:
            if number % m == 0:
                return [number // m, m, 0]
            m -= 1

        rest = number % max_number
        return [(number - rest) // max_number, max_number, rest]

    def _loop_unfold(self):
        factor_1, factor_2, rest = self._calculate_factors(number=self._count(), max_number=self.max_count)
        noop = f'; LOOP UNFOLD: {factor_1} * {factor_2} + {rest} = {self._count()}' + (self.noop or '')
        commands = LightSequenceLoop(objects=[LightSequenceLoop(objects=self, arguments=Arguments([factor_2]))], arguments=Arguments([factor_1]), noop=noop)._resolve_unsupported()
        if rest > 0:
            commands.append(LightSequenceLoop(objects=self, arguments=Arguments([rest])))
        return commands

    def _resolve_unsupported(self):
        self.resolve_unsupported()
        if self._count() == 0:
            return [LightCommandNoop(noop=self.noop)]
        elif self._count() == 1:
            return [LightCommandNoop(noop=self.noop)] + self
        elif self._count() > self.max_count:
            return self._loop_unfold()
        else:
            return [self]

LightSequenceLoop.valid_objects = (
    LightCommandNoop,
    LightCommandColor,
    LightCommandColorRed,
    LightCommandColorGreen,
    LightCommandColorBlue,
    LightCommandRamp,
    LightCommandDelay,
    LightCommandSub,
    LightCommandTime,
    LightSequenceLoop
)


class LightSequenceMain(LightSequence):
    name = 'main'
    command_variants_end = {'legacy': 'END', 'default': 'end'}
    valid_arguments = ((),)
    valid_objects = (
        LightCommandDefine,
        LightCommandNoop,
        LightCommandColor,
        LightCommandColorRed,
        LightCommandColorGreen,
        LightCommandColorBlue,
        LightCommandRamp,
        LightCommandDelay,
        LightCommandSub,
        LightCommandTime,
        LightSequenceLoop
    )


class LightSequenceDefsub(LightSequence):
    name = 'defsub'
    command_variants = {'legacy': 'DEFSUB', 'default': 'defsub', 'camel': 'defSub'}
    command_variants_end = {'legacy': 'ENDSUB', 'default': 'endsub', 'camel': 'endSub'}
    valid_arguments = ((str,),)
    valid_objects = (
        LightCommandNoop,
        LightCommandColor,
        LightCommandColorRed,
        LightCommandColorGreen,
        LightCommandColorBlue,
        LightCommandRamp,
        LightCommandDelay,
        LightCommandSub,
        LightCommandTime,
        LightSequenceLoop
    )
    level_add = 1

    def get_name(self):
        return self.arguments[0]

    def add_namespace(self, namespace):
        super().add_namespace(namespace)
        self.arguments[0] = namespace + self.arguments[0]


class LightSequenceFile(LightSequence):
    name = 'file'
    valid_arguments = ((),)
    valid_objects = (
        LightCommandNoop,
        LightSequenceMain,
        LightSequenceDefsub
    )

    def get_main(self):
        for object in self:
            if isinstance(object, LightSequenceMain):
                return object
        error(f'main sequence not found')

    def get_sub(self, name):
        for object in self:
            if isinstance(object, LightSequenceDefsub) and object.get_name() == name:
                return object
        error(f'sub not found {name}')

    def get_duration(self, root=None):
        return self.get_main().get_duration(root=self)

    def render(self):
        return self.get_main().render(root=self)

    def shift_labels(self, labels):
        main = self.get_main()
        index = 0
        time = 0
        time_ref = 0
        while index < len(main):
            object = main[index]
            if isinstance(object, LightCommandTime):
                objects, time_ref = main[index].resolve(labels, time, time_ref)
                main.pop(index)
                for o in range(len(objects)):
                    main.insert(index + o, objects[o])
                index -= 1
            index += 1
            time += object.get_duration(root=self)

    def compress(self, options):
        options['root'] = self
        super().compress(options=options)

    def merge(self, other):
        self.get_main().extend(list(other.get_main()))
        self.extend(list(filter(lambda o: not isinstance(o, LightSequenceMain), list(other))))


class GloList(list):
    def import_files(self, files, split_number=None):
        # any number of files without splitting
        if split_number is None:
            for f in files:
                print(f'importing \'{f}\'')
                with open(f) as file_object:
                    self.append(self._import_glo(file_object))
        # single file with split
        elif len(files) == 1:
            print(f'importing \'{files[0]}\' ({split_number})')
            for file_object in self._split_file(files[0], split_number):
                self.append(self._import_glo(file_object))
        # multiple files with split
        else:
            # merge multiple files
            for f in range(len(files)):
                print(f'importing/merging \'{files[f]}\' ({split_number})')
                file_objects = self._split_file(files[f], split_number)
                for n in range(split_number):
                    glo = self._import_glo(file_objects[n])
                    glo.add_namespace("G{:02}_".format(f + 1))
                    if f == 0:
                        self.append(glo)
                    else:
                        self[n].merge(glo)

    def _color_row_to_colors(self, row):
        o = []

        color_pre = None
        delay_repeat = 0

        for i in range(0, len(row), 3):
            color = tuple(row[i: i + 3])

            if color == color_pre:
                o.pop()
                delay_repeat += 1
            else:
                o.append(LightCommandColor(arguments=Arguments(color)))
                delay_repeat = 1
            o.append(LightCommandDelay(arguments=Arguments([delay_repeat])))

            color_pre = color

        return o

    def _color_row_to_ramps(self, row):
        o = []

        color_pre = None
        delay_repeat = 1

        for i in range(0, len(row), 3):
            color = tuple(row[i: i + 3])

            if i == 0:
                o.append(LightCommandColor(arguments=Arguments(color)))
            elif color == color_pre:
                if delay_repeat > 1:
                    o.pop()
                o.append(LightCommandRamp(arguments=Arguments(color + (delay_repeat,))))
                delay_repeat += 1
            else:
                delay_repeat = 1
                o.append(LightCommandRamp(arguments=Arguments(color + (1,))))
                color_pre = color

        if delay_repeat > 1:
            o.pop()
        o.append(LightCommandRamp(arguments=Arguments(color + (delay_repeat,))))

        return o

    def import_png(self, filename, ramps):
        print(f'importing png: {filename}')

        r = png.Reader(filename=filename)
        width, height, rows, metadata = r.asRGB8()

        print(f'{width} x {height}')
        print(metadata)

        i = 1

        for row in rows:
            sub_name = "image_{}_{:02}".format(filename.replace('.', '_'), i)
            i += 1

            if ramps:
                o = self._color_row_to_ramps(row)
            else:
                o = self._color_row_to_colors(row)

            objects = [LightSequenceMain(objects=[LightCommandSub(arguments=Arguments([sub_name]))])]
            objects.append(LightSequenceDefsub(arguments=Arguments([sub_name]), objects=o))
            self.append(LightSequenceFile(objects=objects))

    def _split_file(self, file_object, number):
        active = set(range(number))
        handled = set()

        iofiles = []
        for count in range(number):
            iofiles.append(io.StringIO())

        f = open(file_object)

        for line in f:
            m = re.search('^<(.*)>$', line)
            if m:
                split_command = m.group(1)
                n = re.search('^[0-9]*(,[0-9]*)*$', split_command)
                if n:
                    active = set()
                    for a in (map(int, split_command.split(","))):
                        active.add(a - 1)
                    handled.update(active)
                elif split_command == "default":
                    active = set()
                    for count in range(number):
                        if count not in handled:
                            active.add(count)
                elif split_command == "end":
                    active = set(range(number))
                    handled = set()
            else:
                for count in range(number):
                    if count in active:
                        iofiles[count].write(line)

        f.close()

        for count in range(number):
            iofiles[count].seek(0)

        return iofiles

    def _import_glo(self, glo_file):
        constants = {}

        sequence_main = LightSequenceMain()
        self._scan_glo(glo_file, sequence_main, constants=constants)

        sequence_file = LightSequenceFile(objects=[sequence_main])
        self._scan_glo(glo_file, sequence_file, constants=constants)

        return sequence_file

    def _scan_glo(self, glo_file, light_sequence, constants={}):
        command_dict = light_sequence.valid_objects_dict()
        exit_commands = light_sequence.exit_commands()

        for line in glo_file:
            m = re.search('^;(?:L-|LABEL )([-\w]*)(?: ([+-]?[0-9]+))?$', line)
            if m:
                if m.group(2) is not None:
                    line = "time ({}, {}, {}, {})".format('set', 'label', m.group(1), m.group(2))
                else:
                    line = "time ({}, {}, {})".format('set', 'label', m.group(1))

            command, name, arguments, noop = self._split_line(line.rstrip())
            arguments = self._split_arguments(arguments, constants, name)

            if command in exit_commands:
                return

            if command not in command_dict:
                error(f'command "{command}" not allowed in \'{light_sequence.name}\'')

            light_object = command_dict[command](arguments=arguments, noop=noop)
            light_sequence.append(light_object)

            if isinstance(light_object, LightCommandDefine):
                constants[name] = arguments

            if isinstance(light_object, LightSequence):
                self._scan_glo(glo_file, light_object, constants=constants)

        if len(exit_commands) == 0:
            return
        else:
            error(f'end of file reached in \'{light_sequence.name}\'')

    def _split_line(self, line):
        # old syntax: "CMD, 1, 2, 3" / "command, 1, 2, 3"
        m = re.search('^\s*([A-Z]+|[a-z][A-Za-z\.]*)(?:\s*,\s*([^;]*[^;\s]+))?(?:\s*|(\s*;.*))?$', line)
        if m:
            return m.group(1), None, m.group(2), m.group(3)

        # new syntax: "command (1, 2, 3)" / command (CONSTANT)"
        m = re.search('^\s*([a-z][A-Za-z\.]*)(?:\s*\(([^.:#;]*[^.:#;\s]+)\s*\))?(?:\s*|(\s*;.*))?$', line)
        if m:
            return m.group(1), None, m.group(2), m.group(3)

        # define
        m = re.search('^\s*(#define)\s+([^ ]*)\s+([^;]*[^;\s]+)(?:\s*|(\s*;.*))?$', line)
        if m:
            return m.group(1), m.group(2), m.group(3), m.group(4)

        # comment
        m = re.search('^(\s*(?:;.*)?)$', line)
        if m:
            return 'noop', None, None, m.group(1)

        error(f'could not parse line: "{line}"')

    def _split_arguments(self, arguments_str, constants, name):
        arguments = []

        if arguments_str is not None:
            for arg in (a.strip() for a in arguments_str.split(',')):
                try:
                    arg = int(arg)
                except ValueError:
                    pass

                if isinstance(arg, str) and re.match('[A-Z]', arg) and arg in constants.keys():
                    arg = constants[arg]

                arguments.append(arg)

        return Arguments(name=name, objects=arguments)

    def apply_labels(self, labels):
        print("applying labels")
        for glo in self:
            glo.shift_labels(labels)

    def resolve_constants(self):
        print("resolving constants")
        for glo in self:
            glo.resolve_constants()

    def compress(self, options):
        print("compressing sequences")
        for glo in self:
            glo.compress(options)

    def resolve_unsupported(self):
        print("resolving unsupported commands")
        for glo in self:
            glo.resolve_unsupported()

    def strip(self):
        print("stripping comments")
        for glo in self:
            glo.strip()

    def print_glo(self, syntax, indent):
        print('-' * 80)
        for n in range(len(self)):
            glo = self[n]
            try:
                duration = glo.get_duration()
            except ValueError:
                duration = 0
            print(f'#{n + 1:02} - duration: {duration/resolution:.2f} seconds')
            print('-' * 80)
            print(glo.export(syntax=syntax, indent=indent))
            print('-' * 80)

    def export_glo(self, basename, syntax, indent):
        for n in range(len(self)):
            glo = self[n]
            filename = f'{basename}_{n + 1:02}.glo'
            print(f'writing {filename}: {glo.get_duration()/resolution:.2f} seconds')
            with open(filename, 'w') as f:
                f.write(glo.export(syntax=syntax, indent=indent))

    def render_png(self, filename, resolution, stretch, padding, amplify):
        print(f'exporting png: resolution={resolution}, stretch={stretch}, padding={padding}, amplify={amplify}')

        rows = []

        for p in range(padding):
            rows.append([])

        for glo in self:
            rows_x = []
            for i in range(resolution):
                rows_x.append([])

            row = 0
            for c in glo.render():
                rows_x[row].extend(c.get_rgb(amplify))
                row += 1
                if row >= resolution:
                    row = 0

            for row in rows_x:
                for r in range(stretch):
                    rows.append(row)

            for p in range(padding):
                rows.append([])

        max_len = max(len(r) for r in rows)
        for i in range(len(rows)):
            while len(rows[i]) < max_len:
                rows[i].extend([0, 0, 0])

        height = len(rows)
        width = len(rows[0]) // 3

        print(f'writing {filename}: {width} x {height} px')

        f = open(filename, 'wb')
        w = png.Writer(width, height)
        w.write(f, rows)
        f.close()

    def _create_bars(self, slice, bar_width):
        row = []
        for s in slice:
            row.extend(s * bar_width)
            row.extend((0, 0, 0))
        return row[0: -3]

    def _get_slices(self, slices, slice_min, slice_max):
        return (
            list(slices[-1] for t in range(min(slice_min, 0), min(slice_max, 0))) +
            slices[max(slice_min, 0): max(slice_max, 0)] +
            list(slices[-1] for t in range(max(slice_min, len(slices)), max(slice_max, len(slices))))
        )

    def _write_png(self, color_slices, slice_min, slice_max, bar_width, png_writer, pipe):
        slices = self._get_slices(color_slices, slice_min, slice_max)
        png_writer.write(pipe, list(self._create_bars(slice, bar_width) for slice in slices))

    def render_video(self, filename, amplify=False, time_start=0, fps=30, window=10, bar_width=4, audio_file=None, width=640, height=360, preset='fast'):
        num = len(self)
        colors = list(n.render().get_rgb(amplify) for n in self)
        max_length = max(len(n) for n in colors)

        # fill all up to max length
        for n in colors:
            for t in range(max_length - len(n)):
                n.append((0, 0, 0))

        color_slices = []
        for t in range(max_length):
            color_slices.append(list(colors[n][t] for n in range(num)))
        # add a black slice in the end
        color_slices.append(list((0, 0, 0) for n in range(num)))

        render_width = num * (bar_width + 1) - 1
        render_height = window
        time_end = max_length / resolution
        frames_start = int(time_start * fps)
        frames_end = int(time_end * fps)

        print(f'rendering {time_end - time_start:.2f} seconds ({time_start:.2f} - {time_end:.2f}) at {fps} fps: {frames_end - frames_start} frames, {render_width} x {render_height}')

        args = [
            'ffmpeg', '-hide_banner', '-y',
            '-f', 'image2pipe',
            '-c:v', 'png',
            '-r', str(fps),
            '-i', '-',
            '-filter:v', f'scale={width}:{height}',
            '-sws_flags', 'neighbor',
            '-c:v', 'libx264',
            '-preset', preset,
            # '-pix_fmt', 'yuv420p',
            '-b:v', '300k',
            '-c:a', 'copy',
            '-ss', f'{time_start:.2f}',
            '-to', f'{time_end:.2f}',
            filename
        ]

        args_audio = [
            '-i', audio_file
        ]

        if audio_file is not None:
            index = args.index('-i') + 2
            for a in args_audio:
                args.insert(index, a)
                index += 1

        print(f'encoding video: {" ".join(args)}\n')

        w = png.Writer(render_width, render_height)

        with Popen(args, stdin=PIPE) as pipe:
            for frame in range(frames_end):
                t = frame * resolution // fps
                self._write_png(color_slices, t - window + 1, t + 1, bar_width, w, pipe.stdin)


################################################################################

def get_arguments():
    parser = argparse.ArgumentParser()

    group_input = parser.add_mutually_exclusive_group(required=True)
    group_input.add_argument('-input', help='glo input file(s)', dest='input_files', nargs="+", metavar='FILE')
    group_input.add_argument('-import-png', help='png input file', dest='import_png_file', metavar='FILE')
    group_input.add_argument('-convert-labels', help='convert labels', dest='labels_convert', nargs=2, metavar='FILE')

    parser.add_argument('-debug', help='enable debug output', dest='debug', action='store_true')

    group_import_file = parser.add_argument_group('glo file import')
    group_import_file.add_argument('-number', help='split to number of sequences', dest='number', type=int, default=None)

    group_import_png = parser.add_argument_group('png file import')
    group_import_png.add_argument('-import-png-ramps', help=argparse.SUPPRESS, dest='import_png_ramps', action='store_true')

    group_convert = parser.add_argument_group('labels conversion')
    group_convert.add_argument('-labels-format', help='labels conversion output format', dest='labels_convert_format', default='audacity', choices=['audacity', 'markers'])

    group_labels = parser.add_argument_group('labels import')
    group_labels.add_argument('-labels', help='labels file(s)', dest='labels_files', nargs="+", metavar='FILE')

    group_output = parser.add_argument_group('glo file export')
    group_output.add_argument('-print', help='print sequences', dest='print', action='store_true')
    group_output.add_argument('-output', help='output file basename', dest='output_file', metavar='BASENAME')
    group_output.add_argument('-resolve', help='resolve constants', dest='resolve_constants', action='store_true')
    group_output.add_argument('-compress', help='compress command sequences', dest='compress', action='store_true')
    group_output.add_argument('-epsilon', help='maximum color distance for ramp compression', dest='compress_epsilon', type=float, default=1.0, metavar='DISTANCE')
    group_output.add_argument('-unsupported', help='resolve unsupported commands', dest='resolve_unsupported', action='store_true')
    group_output.add_argument('-syntax', help='command syntax to use', dest='syntax', nargs="+", default=[], choices=['legacy', 'british', 'camel', 'call'])
    group_output.add_argument('-tab', help='indention characters', dest='indent', type=int, default=2, metavar='SPACES')
    group_output.add_argument('-strip', help='remove all comments and empty lines', dest='strip', action='store_true')

    group_img_vid = parser.add_argument_group('image & video export')
    group_img_vid.add_argument('-amplify', help='amplify colors in png/video output', dest='amplify', action='store_true')
    group_img_vid.add_argument('-png', help='png output file', dest='png_output_file', metavar='FILE')
    group_img_vid.add_argument('-png-resolution', help='png output horizontal resolution (hundredth seconds per pixel column)', dest='png_output_resolution', type=int, default=12, metavar='RESOLUTION')
    group_img_vid.add_argument('-png-stretch', help='png output vertical stretch factor', dest='png_output_stretch', type=int, default=6, metavar='STRETCH')
    group_img_vid.add_argument('-png-padding', help='png output padding', dest='png_output_padding', type=int, default=6, metavar='PADDING')
    group_img_vid.add_argument('-video', help='video output file', dest='video_output_file', metavar='FILE')
    group_img_vid.add_argument('-video-audio', help='audio file for video output', dest='video_output_audio_file', metavar='FILE')
    group_img_vid.add_argument('-video-fps', help='video output fps', dest='video_output_fps', type=int, default=30, metavar='FPS')
    group_img_vid.add_argument('-video-start-seconds', help='number of seconds to skip in the beginning', dest='video_start_seconds', type=float, default=0, metavar='SECONDS')
    group_img_vid.add_argument('-video-width', help='video output width', dest='video_output_width', type=int, default=320, metavar='WIDTH')
    group_img_vid.add_argument('-video-height', help='video output height', dest='video_output_height', type=int, default=180, metavar='HEIGHT')
    group_img_vid.add_argument('-video-window', help='length of moving time window shown in video (hundredth seconds)', dest='video_output_window', type=int, default=10, metavar='WINDOW')
    group_img_vid.add_argument('-video-bar-width', help='width of bars (relative to margin)', dest='video_output_bar_width', type=int, default=4, metavar='WIDTH')
    group_img_vid.add_argument('-video-preset', help='video encoding preset', dest='video_preset', default='ultrafast', choices=['slow', 'medium', 'fast', 'faster', 'veryfast', 'superfast', 'ultrafast'])

    return parser.parse_args()

def main():
    args = get_arguments()

    global debug
    debug = args.debug

    glo_list = GloList()

    if args.labels_convert:
        labels = Labels([args.labels_convert[0]])
        labels.export_file(args.labels_convert[1], args.labels_convert_format)

    else:

        if args.input_files:
            glo_list.import_files(
                files=args.input_files,
                split_number=args.number
            )

        elif args.import_png_file:
            glo_list.import_png(
                filename=args.import_png_file,
                ramps=args.import_png_ramps
            )

        if args.labels_files:
            glo_list.apply_labels(Labels(args.labels_files))

        if args.resolve_constants:
            glo_list.resolve_constants()

        if args.compress:
            glo_list.compress(
                options={'epsilon': args.compress_epsilon}
            )

        if args.resolve_unsupported:
            glo_list.resolve_unsupported()

        if args.strip:
            glo_list.strip()

        if args.print:
            glo_list.print_glo(
                syntax=args.syntax,
                indent=args.indent
            )

        if args.output_file:
            glo_list.export_glo(
                basename=args.output_file,
                syntax=args.syntax,
                indent=args.indent
            )

        if args.png_output_file:
            glo_list.render_png(
                filename=args.png_output_file,
                resolution=args.png_output_resolution,
                stretch=args.png_output_stretch,
                padding=args.png_output_padding,
                amplify=args.amplify
            )

        if args.video_output_file:
            glo_list.render_video(
                filename=args.video_output_file,
                amplify=args.amplify,
                time_start=args.video_start_seconds,
                fps=args.video_output_fps,
                window=args.video_output_window,
                bar_width=args.video_output_bar_width,
                audio_file=args.video_output_audio_file,
                width=args.video_output_width,
                height=args.video_output_height,
                preset=args.video_preset
            )

if __name__ == "__main__":
    main()
