// pb2folded converts a pprof profile into inferno folded stacks, or into a
// multi-value TSV table carrying every sample type at once.
//
// Heap profiles hold several sample types in a language-specific order
// (Go leads with alloc_objects, gperftools with objects), so folding a fixed
// index renders object counts under a "bytes" label. -select names the wanted
// type explicitly; without it the first value is folded, which is what every
// CPU profile wants.
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/google/pprof/profile"
)

const unknownFrame = "[unknown]"

func main() {
	sel := flag.String("select", "", "comma-separated sample-type name preference list; first match wins")
	unit := flag.String("unit", "", "require the selected sample type to carry this unit")
	table := flag.Bool("table", false, "emit a TSV of every sample type instead of folded stacks")
	flag.Parse()

	if flag.NArg() != 2 {
		fmt.Fprintln(os.Stderr, "usage: pb2folded [-select names] [-unit u] [-table] <in.pb> <out>")
		os.Exit(2)
	}
	if err := run(flag.Arg(0), flag.Arg(1), *sel, *unit, *table); err != nil {
		fmt.Fprintf(os.Stderr, "pb2folded: %v\n", err)
		os.Exit(1)
	}
}

func run(inPath, outPath, sel, unit string, table bool) error {
	f, err := os.Open(inPath)
	if err != nil {
		return err
	}
	defer f.Close()
	// Every producer here gzips; profile.Parse handles that transparently.
	p, err := profile.Parse(f)
	if err != nil {
		return fmt.Errorf("parsing %s: %w", inPath, err)
	}

	out, err := os.Create(outPath)
	if err != nil {
		return err
	}
	w := bufio.NewWriter(out)
	if table {
		err = writeTable(w, p)
	} else {
		var idx int
		if idx, err = selectIndex(p, sel, unit); err == nil {
			err = writeFolded(w, p, idx)
		}
	}
	if err != nil {
		out.Close()
		return err
	}
	if err := w.Flush(); err != nil {
		out.Close()
		return err
	}
	return out.Close()
}

// selectIndex resolves which sample value to fold. Precedence: an explicit
// -select preference list, then the profile's own DefaultSampleType (Go's
// Lookup("allocs") sets it to alloc_space), then index 0.
func selectIndex(p *profile.Profile, sel, unit string) (int, error) {
	if sel != "" {
		for _, want := range strings.Split(sel, ",") {
			want = strings.TrimSpace(want)
			for i, st := range p.SampleType {
				if st.Type != want {
					continue
				}
				if unit != "" && st.Unit != unit {
					return 0, fmt.Errorf("sample type %q has unit %q, wanted %q", st.Type, st.Unit, unit)
				}
				return i, nil
			}
		}
		return 0, fmt.Errorf("none of [%s] present; profile has [%s]", sel, describeTypes(p))
	}
	if p.DefaultSampleType != "" {
		for i, st := range p.SampleType {
			if st.Type == p.DefaultSampleType {
				return i, nil
			}
		}
	}
	if len(p.SampleType) == 0 {
		return 0, fmt.Errorf("profile declares no sample types")
	}
	return 0, nil
}

func describeTypes(p *profile.Profile) string {
	names := make([]string, 0, len(p.SampleType))
	for _, st := range p.SampleType {
		names = append(names, st.Type+"/"+st.Unit)
	}
	return strings.Join(names, ", ")
}

type row struct {
	stack string
	value int64
}

// writeFolded emits `root;…;leaf <value>` lines, descending by value.
//
// Samples are NOT merged by stack string: pprof keys samples on labels as well
// as locations (Go tags each heap sample with its size class), so repeated
// stacks with distinct weights are expected — and are what pprofutils emitted.
// Non-positive values are dropped: selecting inuse_space on a Go heap leaves
// every freed site at zero, which would otherwise render as zero-width frames.
func writeFolded(w *bufio.Writer, p *profile.Profile, idx int) error {
	rows := make([]row, 0, len(p.Sample))
	for _, s := range p.Sample {
		if idx >= len(s.Value) || s.Value[idx] <= 0 {
			continue
		}
		rows = append(rows, row{stack: strings.Join(stackFrames(s), ";"), value: s.Value[idx]})
	}
	sort.SliceStable(rows, func(i, j int) bool {
		if rows[i].value != rows[j].value {
			return rows[i].value > rows[j].value
		}
		return rows[i].stack < rows[j].stack
	})
	for _, r := range rows {
		if _, err := fmt.Fprintf(w, "%s %d\n", r.stack, r.value); err != nil {
			return err
		}
	}
	return nil
}

// writeTable emits a header naming every sample type, then one tab-separated
// row per sample. The runner joins these into the per-frame bucket columns;
// keeping all values in one pass avoids re-reading the profile per type.
func writeTable(w *bufio.Writer, p *profile.Profile) error {
	if _, err := fmt.Fprintf(w, "#stack\t%s\n", strings.Join(typeNames(p), "\t")); err != nil {
		return err
	}
	n := len(p.SampleType)
	// Sort by the last column: for both the Go 4-type and the gperftools
	// 2-type shapes that is the live-bytes bucket, the most useful ordering.
	samples := make([]*profile.Sample, 0, len(p.Sample))
	for _, s := range p.Sample {
		if anyPositive(s.Value) {
			samples = append(samples, s)
		}
	}
	sort.SliceStable(samples, func(i, j int) bool {
		return lastValue(samples[i], n) > lastValue(samples[j], n)
	})
	for _, s := range samples {
		frames := make([]string, 0, len(s.Location))
		for _, f := range stackFrames(s) {
			frames = append(frames, strings.ReplaceAll(f, "\t", " "))
		}
		if _, err := fmt.Fprint(w, strings.Join(frames, ";")); err != nil {
			return err
		}
		for i := 0; i < n; i++ {
			var v int64
			if i < len(s.Value) {
				v = s.Value[i]
			}
			if _, err := fmt.Fprintf(w, "\t%d", v); err != nil {
				return err
			}
		}
		if _, err := fmt.Fprintln(w); err != nil {
			return err
		}
	}
	return nil
}

func typeNames(p *profile.Profile) []string {
	names := make([]string, 0, len(p.SampleType))
	for _, st := range p.SampleType {
		names = append(names, st.Type+"/"+st.Unit)
	}
	return names
}

func anyPositive(vs []int64) bool {
	for _, v := range vs {
		if v > 0 {
			return true
		}
	}
	return false
}

func lastValue(s *profile.Sample, n int) int64 {
	if n == 0 || len(s.Value) < n {
		return 0
	}
	return s.Value[n-1]
}

// stackFrames renders a sample's locations leaf-last, expanding inlined frames.
//
// Locations arrive leaf-first and each Location's Line slice runs
// innermost-first (proto/profile.proto: the last Line is the caller the others
// were inlined into), so both are walked in reverse. Frame text carries no
// decoration — downstream consumers match frame text literally.
func stackFrames(s *profile.Sample) []string {
	frames := make([]string, 0, len(s.Location))
	for i := len(s.Location) - 1; i >= 0; i-- {
		loc := s.Location[i]
		if len(loc.Line) == 0 {
			// Unsymbolized: emit a placeholder rather than nothing, so the
			// stack keeps its depth and the weight still reaches top.txt.
			frames = append(frames, unknownFrame)
			continue
		}
		for j := len(loc.Line) - 1; j >= 0; j-- {
			fn := loc.Line[j].Function
			if fn == nil || fn.Name == "" {
				frames = append(frames, unknownFrame)
				continue
			}
			frames = append(frames, fn.Name)
		}
	}
	return frames
}
