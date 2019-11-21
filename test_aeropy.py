#!/usr/bin/python3

import unittest
import io

from aeropy import Color, Labels, Arguments, LightCommandColor, LightCommandDelay, LightCommandRamp, LightCommandNoop, LightCommandSub, LightCommandDefine, LightSequence, LightSequenceLoop, LightSequenceDefsub, LightSequenceMain, LightSequenceFile, GloList


class TestLabels(unittest.TestCase):
    def test_labels_audacity(self):
        labels = Labels()
        labelsfile = io.StringIO()
        labelsfile.write("29.111111\t31.999999\ta\n")
        labelsfile.write("33.222222\t35.888888\tb\n")
        labelsfile.seek(0)
        labels._import(labelsfile)
        self.assertEqual(labels.label_start("a"), 2911)
        self.assertEqual(labels.label_end("a"), 3199)
        self.assertEqual(labels.label_start("b"), 3322)
        self.assertEqual(labels.label_end("b"), 3588)

    def test_labels_markers_minsec(self):
        labels = Labels()
        labelsfile = io.StringIO()
        labelsfile.write("#,Name,Start\n")
        labelsfile.write("M1,a,0:23.732\n")
        labelsfile.write("M2,b,1:00.125\n")
        labelsfile.seek(0)
        labels._import(labelsfile)
        self.assertEqual(labels.label_start("a"), 2373)
        self.assertEqual(labels.label_end("a"), 2373)
        self.assertEqual(labels.label_start("b"), 6012)
        self.assertEqual(labels.label_end("b"), 6012)

    def test_labels_markers_seconds(self):
        labels = Labels()
        labelsfile = io.StringIO()
        labelsfile.write("#,Name,Start\n")
        labelsfile.write("M1,a,23.732\n")
        labelsfile.write("M2,b,60.125\n")
        labelsfile.seek(0)
        labels._import(labelsfile)
        self.assertEqual(labels.label_start("a"), 2373)
        self.assertEqual(labels.label_end("a"), 2373)
        self.assertEqual(labels.label_start("b"), 6012)
        self.assertEqual(labels.label_end("b"), 6012)

    def test_labels_markers_beatsbars(self):
        labels = Labels()
        labelsfile = io.StringIO()
        labelsfile.write("#,Name,Start\n")
        labelsfile.write("M1,a,12.4.47\n")
        labelsfile.write("M2,b,31.1.25\n")
        labelsfile.seek(0)
        labels._import(labelsfile)
        self.assertEqual(labels.label_start("a"), 2373)
        self.assertEqual(labels.label_end("a"), 2373)
        self.assertEqual(labels.label_start("b"), 6012)
        self.assertEqual(labels.label_end("b"), 6012)


class TestColor(unittest.TestCase):
    def test_list(self):
        cr = Color(255, 255, 255)
        self.assertEqual(cr.get_rgb(), (255, 255, 255))

    def test_add(self):
        c1 = Color(10, 20, 30)
        c2 = Color(2, 4, 6)
        cr = c1 + c2
        self.assertEqual(cr.get_rgb(), (12, 24, 36))

    def test_sub(self):
        c1 = Color(10, 20, 30)
        c2 = Color(2, 4, 6)
        cr = c1 - c2
        self.assertEqual(cr.get_rgb(), (8, 16, 24))

    def test_mul(self):
        c1 = Color(10, 20, 30)
        cr = c1 * 2
        self.assertEqual(cr.get_rgb(), (20, 40, 60))

    def test_round(self):
        c1 = Color(10.9, 20.1, 30.5)
        cr = round(c1)
        self.assertEqual(cr.get_rgb(), (11, 20, 30))

    def test_abs(self):
        c1 = Color(-100, 0, 10.5)
        cr = abs(c1)
        self.assertEqual(cr.get_rgb(), (100, 0, 10.5))

    def test_eq(self):
        c1 = Color(255, 0, 0)
        c2 = Color(255, 0, 0)
        self.assertEqual(c1, c2)

    def test_or(self):
        c1 = Color(255, None, None)
        c2 = Color(10, 20, None)
        cr = c1 | c2
        self.assertEqual(cr.get_rgb(), (255, 20, None))

    def test_amplify(self):
        c = Color(10, 20, 30)
        self.assertEqual(c.get_rgb(amplify=True), (50, 71, 87))

    def test_distance(self):
        c_k = Color(0, 0, 0)
        c_r = Color(255, 0, 0)
        c_g = Color(0, 255, 0)
        c_b = Color(0, 0, 255)
        c_y = Color(255, 255, 0)
        c_m = Color(255, 0, 255)
        c_c = Color(0, 255, 255)
        c_w = Color(255, 255, 255)
        self.assertEqual(c_k.distance(c_r), 255)
        self.assertEqual(c_r.distance(c_k), 255)
        self.assertEqual(round(c_k.distance(c_c)), 361)
        self.assertEqual(round(c_k.distance(c_w)), 442)
        self.assertEqual(round(c_r.distance(c_c)), 442)
        self.assertEqual(round(c_g.distance(c_m)), 442)
        self.assertEqual(round(c_b.distance(c_y)), 442)


class TestArguments(unittest.TestCase):
    def test_arguments(self):
        a1 = Arguments([1, 2, 3])
        a2 = Arguments([4, 5, 6], name="a2")
        a3 = Arguments([a2, 10])
        a4 = Arguments([a2, 20], name="a4")
        self.assertEqual(str(a1), "1, 2, 3")
        self.assertEqual(str(a2), "a2")
        self.assertEqual(str(a3), "a2, 10")
        self.assertEqual(str(a4), "a4")
        self.assertEqual(a1._expand(), [1, 2, 3])
        self.assertEqual(a2._expand(), [4, 5, 6])
        self.assertEqual(a3._expand(), [4, 5, 6, 10])
        self.assertEqual(a4._expand(), [4, 5, 6, 20])


class TestLightObject(unittest.TestCase):
    def test_light_object_color(self):
        c = LightCommandColor(arguments=Arguments([1, 2, 3]), noop=" ; comment")
        self.assertEqual(c.get_duration(), 0)
        self.assertEqual(c.export(), "color (1, 2, 3) ; comment")

    def test_light_object_delay(self):
        d = LightCommandDelay(arguments=Arguments([1]), noop=" ; comment")
        self.assertEqual(d.get_duration(), 1)
        self.assertEqual(d.export(), "delay (1) ; comment")

    def test_light_object_ramp(self):
        r = LightCommandRamp(arguments=Arguments([1, 2, 3, 4]), noop=" ; comment")
        self.assertEqual(r.get_duration(), 4)
        self.assertEqual(r.export(), "ramp (1, 2, 3, 4) ; comment")

    def test_light_object_noop(self):
        n = LightCommandNoop(noop="; comment")
        self.assertEqual(n.get_duration(), 0)
        self.assertEqual(n.export(), "; comment")

    def test_light_object_sub(self):
        d = LightCommandDelay(arguments=Arguments([1]), noop=" ; comment")
        ds = LightSequenceDefsub(arguments=Arguments(['sub_name']), objects=[d], noop=' ; defsub')
        s = LightCommandSub(arguments=Arguments(['sub_name']), noop=" ; comment")
        m = LightSequenceMain(objects=[s])
        f = LightSequenceFile(objects=[m, ds])
        lo = LightSequenceLoop(arguments=Arguments([5]), objects=[s])

        self.assertEqual(ds.export(), "defsub (sub_name) ; defsub\ndelay (1) ; comment\nendsub")
        self.assertEqual(ds.get_duration(), 1)

        self.assertEqual(s.export(), "sub (sub_name) ; comment")
        self.assertEqual(s.get_duration(root=f), 1)

        self.assertEqual(m.export(), "sub (sub_name) ; comment\nend")
        self.assertEqual(m.get_duration(root=f), 1)

        self.assertEqual(f.export(), "sub (sub_name) ; comment\nend\ndefsub (sub_name) ; defsub\ndelay (1) ; comment\nendsub")
        self.assertEqual(f.get_duration(), 1)

        self.assertEqual(lo.export(), "loop (5)\nsub (sub_name) ; comment\nendloop")
        self.assertEqual(lo.get_duration(root=f), 5)

        m.append(lo)
        self.assertEqual(f.get_duration(), 6)


class Test_define(unittest.TestCase):
    def test_define(self):
        arguments = Arguments(name="DEF_NAME", objects=[1, 2, 3])

        define = LightCommandDefine(arguments=arguments)
        color = LightCommandColor(arguments=arguments)
        main = LightSequenceMain(objects=[define, color])

        self.assertEqual(define.export(), "#define DEF_NAME 1, 2, 3")
        self.assertEqual(color.export(), "color (DEF_NAME)")

        main.add_namespace("GLO1_")
        self.assertEqual(main[0].export(), "#define GLO1_DEF_NAME 1, 2, 3")
        self.assertEqual(main[1].export(), "color (GLO1_DEF_NAME)")

        main.resolve_constants()
        self.assertEqual(main[0].export(), ";#define GLO1_DEF_NAME 1, 2, 3")
        self.assertEqual(main[1].export(), "color (1, 2, 3)")


class Test_defsub(unittest.TestCase):
    def test_defsub(self):
        sub = LightCommandSub(arguments=Arguments(objects=["sub_name"]))
        ds = LightSequenceDefsub(arguments=Arguments(objects=["sub_name"]))

        self.assertEqual(sub.export(), "sub (sub_name)")
        self.assertEqual(ds.export(), "defsub (sub_name)\nendsub")

        sub.add_namespace("GLO1_")
        ds.add_namespace("GLO1_")

        self.assertEqual(sub.export(), "sub (GLO1_sub_name)")
        self.assertEqual(ds.export(), "defsub (GLO1_sub_name)\nendsub")


class Test_merge(unittest.TestCase):
    test_file1 = (
        "#define COLOR1 10, 10, 10",
        "sub (sub1)",
        "end",
        "defsub (sub1)",
        "color (COLOR1)",
        "endsub"
    )
    test_file2 = (
        "#define COLOR1 20, 20, 20",
        "sub (sub1)",
        "end",
        "defsub (sub1)",
        "color (COLOR1)",
        "endsub",
    )
    test_output = (
        "#define G0_COLOR1 10, 10, 10",
        "sub (G0_sub1)",
        "#define G1_COLOR1 20, 20, 20",
        "sub (G1_sub1)",
        "end",
        "defsub (G0_sub1)",
        "color (G0_COLOR1)",
        "endsub",
        "defsub (G1_sub1)",
        "color (G1_COLOR1)",
        "endsub"
    )

    def test_merge(self):
        file1 = io.StringIO()
        file1.write('\n'.join(self.test_file1))
        file1.seek(0)

        file2 = io.StringIO()
        file2.write('\n'.join(self.test_file2))
        file2.seek(0)

        g = GloList()
        glo1 = g._import_glo(file1)
        glo1.add_namespace('G0_')
        glo2 = g._import_glo(file2)
        glo2.add_namespace('G1_')
        glo1.merge(glo2)

        self.assertEqual(glo1.export(), '\n'.join(self.test_output))


class Test_resolve_unsupported(unittest.TestCase):
    def test_delay_zero(self):
        delay = LightCommandDelay(arguments=Arguments([0]), noop=" ; comment")
        main = LightSequenceMain(objects=[delay])
        main.resolve_unsupported()

        self.assertEqual(main.export(), "; DELAY RESOLVE: 0 ; comment\nend")

    def test_delay_split(self):
        delay = LightCommandDelay(arguments=Arguments([132000]))
        main = LightSequenceMain(objects=[delay])
        main.resolve_unsupported()

        self.assertEqual(main.export(), "; DELAY RESOLVE: 132000\ndelay (65535)\ndelay (65535)\ndelay (930)\nend")

    def test_loop_unfold(self):
        delay = LightCommandDelay(arguments=Arguments([10]))

        mains = []
        for l in (0, 1, 255, 521):
            loop = LightSequenceLoop(objects=[delay], arguments=Arguments([l]))
            mains.append(LightSequenceMain(objects=[loop]))
            mains[-1].resolve_unsupported()

        self.assertEqual(mains[0].export(), "end")
        self.assertEqual(mains[1].export(), "delay (10)\nend")
        self.assertEqual(mains[2].export(), "loop (255)\ndelay (10)\nendloop\nend")
        self.assertEqual(mains[3].export(), "loop (2); LOOP UNFOLD: 2 * 255 + 11 = 521\nloop (255)\ndelay (10)\nendloop\nendloop\nloop (11)\ndelay (10)\nendloop\nend")


class Test_find_repeated_ngrams(unittest.TestCase):
    def test_find_repeated_ngrams(self):
        s = LightSequence()
        self.assertEqual(s._find_repeated_ngrams([1, 2, 3, 1, 2, 3]), {(1, 2): [0, 3], (2, 3): [1, 4], (1, 2, 3): [0, 3]})
        self.assertEqual(s._find_repeated_ngrams([1, 1, 1, 1, 1]), {(1, 1): [0, 2]})
        self.assertEqual(s._find_repeated_ngrams([1, 1, 1, 1, 1, 1]), {(1, 1): [0, 2, 4], (1, 1, 1): [0, 3]})


class Test_find_repeated_ngrams_grouped(unittest.TestCase):
    def test_find_repeated_ngrams_grouped(self):
        s = LightSequence()
        self.assertEqual(s._find_repeated_ngrams_grouped([1, 2, 3, 1, 2, 3]), {(1, 2): [[0], [3]], (2, 3): [[1], [4]], (1, 2, 3): [[0, 3]]})
        self.assertEqual(s._find_repeated_ngrams_grouped([1, 2, 1, 2, 3, 1, 2]), {(1, 2): [[0, 2], [5]]})
        self.assertEqual(s._find_repeated_ngrams_grouped([1, 1, 1, 1, 1, 1]), {(1, 1): [[0, 2, 4]], (1, 1, 1): [[0, 3]]})


class Test_split_line(unittest.TestCase):
    def test_split_line(self):
        self.assertEqual(GloList._split_line(None, ";"), ('noop', None, None, ';'))
        self.assertEqual(GloList._split_line(None, "C, 1, 2, 3"), ('C', None, '1, 2, 3', None))
        self.assertEqual(GloList._split_line(None, "   color , 1, 2, 3 "), ('color', None, '1, 2, 3', None))
        self.assertEqual(GloList._split_line(None, "color   (1, 2, 3)  ;  comment "), ('color', None, '1, 2, 3', '  ;  comment '))
        self.assertEqual(GloList._split_line(None, "color ( 1, 2, 3)"), ('color', None, ' 1, 2, 3', None))
        self.assertEqual(GloList._split_line(None, "color ( 1 , 2 , 3 )"), ('color', None, ' 1 , 2 , 3', None))
        self.assertEqual(GloList._split_line(None, "#define NAME 1, 2, 3 ; comment"), ('#define', 'NAME', '1, 2, 3', ' ; comment'))


class Test_get_slices(unittest.TestCase):
    def test_get_slices(self):
        s = [1, 2, 3, 4, 0]
        self.assertEqual(GloList._get_slices(None, s, -3, 0), [0, 0, 0])
        self.assertEqual(GloList._get_slices(None, s, -2, 1), [0, 0, 1])
        self.assertEqual(GloList._get_slices(None, s, -1, 2), [0, 1, 2])
        self.assertEqual(GloList._get_slices(None, s, 0, 3), [1, 2, 3])
        self.assertEqual(GloList._get_slices(None, s, 1, 4), [2, 3, 4])
        self.assertEqual(GloList._get_slices(None, s, 2, 5), [3, 4, 0])
        self.assertEqual(GloList._get_slices(None, s, 3, 6), [4, 0, 0])
        self.assertEqual(GloList._get_slices(None, s, 4, 7), [0, 0, 0])


if __name__ == '__main__':
    unittest.main()
