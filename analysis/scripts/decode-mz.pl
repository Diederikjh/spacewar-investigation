#!/usr/bin/env perl

use strict;
use warnings;

my ($path) = @ARGV;
die "usage: $0 FILE\n" unless defined $path;

open my $fh, '<:raw', $path or die "cannot open $path: $!\n";
local $/;
my $data = <$fh>;
close $fh;

my $size = length $data;
die "file is too short for a DOS header\n" if $size < 28;

sub word_at {
    my ($offset) = @_;
    return unpack 'v', substr($data, $offset, 2);
}

sub dword_at {
    my ($offset) = @_;
    return unpack 'V', substr($data, $offset, 4);
}

my %h = (
    magic       => substr($data, 0, 2),
    last_bytes  => word_at(2),
    pages       => word_at(4),
    relocations => word_at(6),
    header_pars => word_at(8),
    min_alloc   => word_at(10),
    max_alloc   => word_at(12),
    ss          => word_at(14),
    sp          => word_at(16),
    checksum    => word_at(18),
    ip          => word_at(20),
    cs          => word_at(22),
    reloc_off   => word_at(24),
    overlay     => word_at(26),
);

my $declared_size = $h{last_bytes} == 0
    ? $h{pages} * 512
    : ($h{pages} - 1) * 512 + $h{last_bytes};
my $header_size = $h{header_pars} * 16;
my $module_size = $declared_size - $header_size;
my $entry_linear = $h{cs} * 16 + $h{ip};
my $stack_linear = $h{ss} * 16 + $h{sp};

printf "File: %s\n", $path;
printf "Actual file size: %d bytes (0x%X)\n", $size, $size;
printf "Magic: %s (hex %s)\n", $h{magic}, unpack('H*', $h{magic});
printf "Bytes in last 512-byte page: %d (0x%04X)\n", $h{last_bytes}, $h{last_bytes};
printf "512-byte pages: %d (0x%04X)\n", $h{pages}, $h{pages};
printf "Declared executable size: %d bytes (0x%X)\n", $declared_size, $declared_size;
printf "Header paragraphs: %d\n", $h{header_pars};
printf "Header size: %d bytes (0x%X)\n", $header_size, $header_size;
printf "Load-module size: %d bytes (0x%X)\n", $module_size, $module_size;
printf "Relocations: %d\n", $h{relocations};
printf "Relocation-table offset: 0x%04X\n", $h{reloc_off};
printf "Minimum extra paragraphs: %d (%d bytes)\n", $h{min_alloc}, $h{min_alloc} * 16;
printf "Maximum extra paragraphs: %d (%d bytes)\n", $h{max_alloc}, $h{max_alloc} * 16;
printf "Initial CS:IP: %04X:%04X\n", $h{cs}, $h{ip};
printf "Entry offset within load module: 0x%05X\n", $entry_linear;
printf "Initial SS:SP: %04X:%04X\n", $h{ss}, $h{sp};
printf "Initial stack position within load module: 0x%05X\n", $stack_linear;
printf "Checksum: 0x%04X\n", $h{checksum};
printf "Overlay number: %d\n", $h{overlay};
printf "Bytes after declared executable image: %d\n", $size - $declared_size;

if ($size >= 64) {
    my $new_header = dword_at(60);
    printf "e_lfanew candidate: 0x%08X\n", $new_header;
    if ($new_header > 0 && $new_header + 2 <= $size) {
        my $signature = substr($data, $new_header, 4);
        printf "Secondary-header bytes: %s", unpack('H*', $signature);
        if ($signature =~ /\A(?:NE|LE|LX|PE\x00\x00)/) {
            printf " (%s)", substr($signature, 0, 2);
        }
        print "\n";
    }
}

if ($h{relocations} > 0) {
    print "Relocation entries (segment:offset within load module):\n";
    for my $index (0 .. $h{relocations} - 1) {
        my $offset = $h{reloc_off} + $index * 4;
        if ($offset + 4 > $size) {
            printf "  [%d] outside file at 0x%X\n", $index, $offset;
            last;
        }
        my ($rel_off, $rel_seg) = unpack 'vv', substr($data, $offset, 4);
        printf "  [%d] %04X:%04X (linear 0x%05X)\n",
            $index, $rel_seg, $rel_off, $rel_seg * 16 + $rel_off;
    }
}

print "Validation:\n";
printf "  Magic is MZ/ZM: %s\n", $h{magic} eq 'MZ' || $h{magic} eq 'ZM' ? 'yes' : 'no';
printf "  Declared size matches actual: %s\n", $declared_size == $size ? 'yes' : 'no';
printf "  Header fits declared image: %s\n", $header_size <= $declared_size ? 'yes' : 'no';
printf "  Entry lies in load module: %s\n", $entry_linear < $module_size ? 'yes' : 'no';
printf "  Relocation table fits header: %s\n",
    $h{reloc_off} + $h{relocations} * 4 <= $header_size ? 'yes' : 'no';

