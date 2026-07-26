package main

import (
	"bufio"
	"io"
	"strings"
	"testing"

	"github.com/google/pprof/profile"
)

func newWriter(w io.Writer) *bufio.Writer { return bufio.NewWriter(w) }

func valueTypes(pairs ...string) []*profile.ValueType {
	vts := make([]*profile.ValueType, 0, len(pairs)/2)
	for i := 0; i < len(pairs); i += 2 {
		vts = append(vts, &profile.ValueType{Type: pairs[i], Unit: pairs[i+1]})
	}
	return vts
}

// goHeap is the 4-type shape runtime/pprof emits — and also the shape pprof's
// legacy parser gives a gperftools dump once its alloc counters diverge from
// in-use. The other shapes under test are spelled inline: gperftools' 2-type
// set, a single-type profile, and the CPU pair.
func goHeap() []*profile.ValueType {
	return valueTypes("alloc_objects", "count", "alloc_space", "bytes",
		"inuse_objects", "count", "inuse_space", "bytes")
}

func TestSelectIndex(t *testing.T) {
	tests := []struct {
		name    string
		types   []*profile.ValueType
		deflt   string
		sel     string
		unit    string
		want    int
		wantErr bool
	}{
		{name: "go heap inuse", types: goHeap(), sel: "inuse_space,space", unit: "bytes", want: 3},
		{name: "go heap alloc", types: goHeap(), sel: "alloc_space", unit: "bytes", want: 1},
		{
			name:  "cpp 2-type falls through to space",
			types: valueTypes("objects", "count", "space", "bytes"),
			sel:   "inuse_space,space", unit: "bytes", want: 1,
		},
		{name: "cpp 4-type prefers inuse_space", types: goHeap(), sel: "inuse_space,space", unit: "bytes", want: 3},
		{
			name:  "single sample type",
			types: valueTypes("inuse_space", "bytes"),
			sel:   "inuse_space,space", unit: "bytes", want: 0,
		},
		{
			name:  "cpu profile resolves and does not error",
			types: valueTypes("samples", "count", "cpu", "nanoseconds"),
			sel:   "samples", unit: "count", want: 0,
		},
		{
			name:  "no selector defaults to index 0",
			types: goHeap(), want: 0,
		},
		{
			name:  "DefaultSampleType outranks index 0",
			types: goHeap(), deflt: "alloc_space", want: 1,
		},
		{
			name:  "explicit selector outranks DefaultSampleType",
			types: goHeap(), deflt: "alloc_space", sel: "inuse_space", want: 3,
		},
		{
			name:  "absent type errors",
			types: valueTypes("samples", "count"),
			sel:   "inuse_space,space", unit: "bytes", wantErr: true,
		},
		{
			name:  "unit mismatch errors",
			types: valueTypes("inuse_space", "count"),
			sel:   "inuse_space", unit: "bytes", wantErr: true,
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			p := &profile.Profile{SampleType: tc.types, DefaultSampleType: tc.deflt}
			got, err := selectIndex(p, tc.sel, tc.unit)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected an error, got index %d", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tc.want {
				t.Errorf("index = %d, want %d", got, tc.want)
			}
		})
	}
}

func fn(name string) *profile.Function { return &profile.Function{Name: name} }

func TestStackFramesOrdersLeafLast(t *testing.T) {
	// Locations arrive leaf-first; the leaf here is inlined two deep.
	leaf := &profile.Location{Line: []profile.Line{
		{Function: fn("memcpy")}, // innermost
		{Function: fn("printf")}, // the caller it was inlined into
	}}
	root := &profile.Location{Line: []profile.Line{{Function: fn("main")}}}
	s := &profile.Sample{Location: []*profile.Location{leaf, root}}

	got := strings.Join(stackFrames(s), ";")
	if want := "main;printf;memcpy"; got != want {
		t.Errorf("stackFrames = %q, want %q", got, want)
	}
}

func TestStackFramesUnsymbolized(t *testing.T) {
	s := &profile.Sample{Location: []*profile.Location{
		{}, // no Line entries at all
		{Line: []profile.Line{{Function: fn("main")}}},
	}}
	got := strings.Join(stackFrames(s), ";")
	if want := "main;" + unknownFrame; got != want {
		t.Errorf("stackFrames = %q, want %q", got, want)
	}
}

func foldToString(t *testing.T, p *profile.Profile, idx int) string {
	t.Helper()
	var sb strings.Builder
	w := newWriter(&sb)
	if err := writeFolded(w, p, idx); err != nil {
		t.Fatalf("writeFolded: %v", err)
	}
	if err := w.Flush(); err != nil {
		t.Fatalf("flush: %v", err)
	}
	return sb.String()
}

func TestWriteFoldedDropsNonPositiveAndSortsDescending(t *testing.T) {
	loc := func(name string) *profile.Location {
		return &profile.Location{Line: []profile.Line{{Function: fn(name)}}}
	}
	p := &profile.Profile{
		SampleType: goHeap(),
		Sample: []*profile.Sample{
			// inuse_space (index 3) is zero: a site that was freed.
			{Location: []*profile.Location{loc("freed")}, Value: []int64{5, 500, 0, 0}},
			{Location: []*profile.Location{loc("small")}, Value: []int64{1, 100, 1, 100}},
			{Location: []*profile.Location{loc("big")}, Value: []int64{2, 900, 2, 900}},
			{Location: []*profile.Location{loc("negative")}, Value: []int64{1, 1, 1, -7}},
		},
	}
	got := foldToString(t, p, 3)
	want := "big 900\nsmall 100\n"
	if got != want {
		t.Errorf("writeFolded =\n%q\nwant\n%q", got, want)
	}
}

func TestWriteFoldedKeepsDuplicateStacksSeparate(t *testing.T) {
	// Go tags heap samples with their size class, so the same call site
	// legitimately appears as several samples. pprofutils never merged them.
	loc := &profile.Location{Line: []profile.Line{{Function: fn("Grow")}}}
	p := &profile.Profile{
		SampleType: goHeap(),
		Sample: []*profile.Sample{
			{Location: []*profile.Location{loc}, Value: []int64{1, 1024, 1, 1024}},
			{Location: []*profile.Location{loc}, Value: []int64{1, 64, 1, 64}},
		},
	}
	got := foldToString(t, p, 3)
	if want := "Grow 1024\nGrow 64\n"; got != want {
		t.Errorf("writeFolded =\n%q\nwant\n%q", got, want)
	}
}

func TestWriteTableEmitsEveryBucket(t *testing.T) {
	loc := &profile.Location{Line: []profile.Line{{Function: fn("Grow")}}}
	p := &profile.Profile{
		SampleType: goHeap(),
		Sample: []*profile.Sample{
			{Location: []*profile.Location{loc}, Value: []int64{7, 700, 3, 300}},
		},
	}
	var sb strings.Builder
	w := newWriter(&sb)
	if err := writeTable(w, p); err != nil {
		t.Fatalf("writeTable: %v", err)
	}
	if err := w.Flush(); err != nil {
		t.Fatalf("flush: %v", err)
	}
	lines := strings.Split(strings.TrimRight(sb.String(), "\n"), "\n")
	wantHeader := "#stack\talloc_objects/count\talloc_space/bytes\tinuse_objects/count\tinuse_space/bytes"
	if lines[0] != wantHeader {
		t.Errorf("header = %q, want %q", lines[0], wantHeader)
	}
	if want := "Grow\t7\t700\t3\t300"; lines[1] != want {
		t.Errorf("row = %q, want %q", lines[1], want)
	}
}
