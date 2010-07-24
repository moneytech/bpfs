#!/usr/bin/env python

# This file is part of BPFS. BPFS is copyright 2009-2010 The Regents of the
# University of California. It is distributed under the terms of version 2
# of the GNU GPL. See the file LICENSE for details.

# TODO:
# - try with different types of file systems
#   (eg many inodes or dirents or large file)
# - create dir/file cases that are not SCSP optimal (that must CoW some)?

import inspect
import getopt
import os
import subprocess
import stat
import sys
import tempfile
import time

class benchmarks:
    @staticmethod
    def all():
        for name, obj in inspect.getmembers(benchmarks):
            if inspect.isclass(obj):
                yield (name, obj)

    class empty:
        opt = 0
        def run(self):
            pass

    class create:
        #     dirent + ino                 + cmtime + d.ft + d.ino
        opt = 4+1+2  + 8+4+4+4+4+8+8+8+3*4 + 4+4    + 1    + 8
        def run(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()

    class mkdir:
        #     dirent + ino                 + cmtime + root + nlinks + nbytes + rl + d.ft + nlinks + d.ino
        opt = 4+1+2  + 8+4+4+4+4+8+8+8+3*4 + 4+4    + 8    + 4      + 8      + 2  + 1    + 4      + 8
        def run(self):
            os.mkdir(os.path.join(self.mnt, 'a'))

    class unlink_0B:
        #     dirent.ino + cmtime
        opt = 8          + 8
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            os.unlink(os.path.join(self.mnt, 'a'))

    class unlink_4k:
        #     dirent.ino + cmtime
        opt = 8          + 8
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            file.write('0' * 4096)
            file.close()
        def run(self):
            os.unlink(os.path.join(self.mnt, 'a'))

    class unlink_1M:
        #     dirent.ino + cmtime
        opt = 8          + 8
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(1 * 64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            os.unlink(os.path.join(self.mnt, 'a'))

    class unlink_16M:
        #     dirent.ino + cmtime
        opt = 8          + 8
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(16 * 64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            os.unlink(os.path.join(self.mnt, 'a'))

    class rmdir:
        #     nlinks + dirent.ino + cmtime
        opt = 4      + 8          + 8
        def prepare(self):
            os.mkdir(os.path.join(self.mnt, 'a'))
        def run(self):
            os.rmdir(os.path.join(self.mnt, 'a'))

    class rename_intra:
        # TODO: could reduce dirent block by 2*8 and by unused
        #     inos + dirents + ino_root + cmtime + rec_len + dirent
        opt = 2*8  + 4096    + 8        + 2*4    + 2       + 2+1+2+1
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            os.rename(os.path.join(self.mnt, 'a'), os.path.join(self.mnt, 'b'))

    class rename_inter:
        # TODO: could reduce dirent blocks by 2*8 and by unused
        # TODO: could reduce ino_roots by 2*8 and by unused
        #     inos + dirents + ino_roots+ ira + cmtime + rec_len + dirent
        opt = 2*8  + 2*4096  + 4096+2*8 + 8   + 4*4    + 2       + 2+1+2+1
        def prepare(self):
            os.mkdir(os.path.join(self.mnt, 'a'))
            os.mkdir(os.path.join(self.mnt, 'b'))
            open(os.path.join(self.mnt, 'a', 'c'), 'w').close()
        def run(self):
            os.rename(os.path.join(self.mnt, 'a', 'c'),
                      os.path.join(self.mnt, 'b', 'c'))

    class rename_clobber:
        # TODO: could reduce dirent blocks by 2*8 and by unused
        # TODO: could reduce ino_roots by 2*8 and by unused
        #     inos + dirents + ino_root + cmtime
        opt = 2*8  + 4096    + 8        + 2*4
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
            open(os.path.join(self.mnt, 'b'), 'w').close()
        def run(self):
            os.rename(os.path.join(self.mnt, 'a'), os.path.join(self.mnt, 'b'))

    class link:
        #     dirent + cmtime + nlinks + ctime + d.ft + d.ino
        opt = 4+1+2  + 8      + 4      + 4     + 1    + 8
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            os.link(os.path.join(self.mnt, 'a'), os.path.join(self.mnt, 'b'))

    class unlink_hardlink:
        #     dirent.ino + cmtime + nlinks + ctime
        opt = 8          + 8      + 4      + 4
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
            os.link(os.path.join(self.mnt, 'a'), os.path.join(self.mnt, 'b'))
        def run(self):
            os.unlink(os.path.join(self.mnt, 'a'))

    class chmod:
        #     mode + ctime
        opt = 4    + 4
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            os.chmod(os.path.join(self.mnt, 'a'), stat.S_IWUSR | stat.S_IRUSR)

    class append_0B_8B:
        #     data + root + size + mtime
        opt = 8    + 8    + 8    + 4
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'a')
            file.write('0' * 8)
            file.close()

    class append_8B_8B:
        #     data + size + mtime
        opt = 8    + 8    + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            file.write('0' * 8)
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'a')
            file.write('0' * 8)
            file.close()

    class append_0B_4k:
        #     data + root + size + mtime
        opt = 4096 + 8    + 8    + 4
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'a')
            file.write('0' * 4096)
            file.close()

    # 128kiB is the largest that FUSE will atomically write
    class append_0B_128k:
        # TODO: changing height separately from root is needless
        #     data     + indir   + height + root + size + mtime
        opt = 128*1024 + 128/4*8 + 8      + 8    + 8    + 4
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'a')
            file.write('0' * (128 * 1024))
            file.close()

    class append_2M_4k:
        #     data + nr + or + in0 + in1 + size + mtime
        opt = 4096 + 8  + 8  + 8   + 8   + 8    + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(2 * 64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'a')
            file.write('0' * 4096)
            file.close()

    # 128kiB is the largest that FUSE will atomically write
    class append_2M_128k:
        #     data     + indir1  + indir0 + root addr/height + size + mtime
        opt = 128*1024 + 128/4*8 + 2*8    + 8                + 8    + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(2 * 64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'a')
            file.write('0' * (128 * 1024))
            file.close()

    class write_1M_8B:
        #     data + mtime
        opt = 8    + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r+', 0)
            file.write('0' * 8)
            file.close()

    class write_1M_8B_4092:
        #     dCoW     + data + iCoW  + indir + mtime
        opt = 2*4096-8 + 8    + 4096  + 2*8+8 + 4
        # extra: iCoW+16
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r+', 0)
            file.seek(4096 - 4)
            file.write('0' * 8)
            file.close()

    class write_1M_16B:
        #     CoW     + indir + data  + mtime
        opt = 4096-16 + 8     + 16    + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r+', 0)
            file.write('0' * 16)
            file.close()

    class write_1M_4k:
        #     data + indir + mtime
        opt = 4096 + 8     + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r+', 0)
            file.write('0' * 4096)
            file.close()

    class write_1M_4k_1:
        #     CoW data    + data + indir      + mtime
        opt = 2*4096-4096 + 4096 + 4096+2*8+8 + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r+', 0)
            file.seek(1)
            file.write('0' * 4096)
            file.close()

    # 128kiB is the largest that FUSE will atomically write
    class write_1M_128k:
        # TODO: avoid CoWing indir slots that will be overwritten
        #     data     + indir   + iCoW + root + mtime
        opt = 128*1024 + 128/4*8 + 4096 + 8    + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r+', 0)
            file.write('0' * (128 * 1024))
            file.close()

    # 128kiB is the largest that FUSE will atomically write
    class write_1M_124k_1:
        # TODO: avoid CoWing indir slots that will be overwritten
        #     dCoW   + data     + indir   + iCoW + root + mtime
        opt = 1+4095 + 124*1024 + 128/4*8 + 4096 + 8    + 4
        def prepare(self):
            file = open(os.path.join(self.mnt, 'a'), 'w')
            for i in range(64):
                file.write('0' * (16 * 1024))
            file.close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r+', 0)
            file.seek(1)
            file.write('0' * (124 * 1024))
            file.close()

    class read:
        #     mtime
        opt = 4
        def prepare(self):
            open(os.path.join(self.mnt, 'a'), 'w').close()
        def run(self):
            file = open(os.path.join(self.mnt, 'a'), 'r')
            file.read(1)
            file.close()

    class readdir:
        #     mtime + mtime
        opt = 4     + 4
        def run(self):
            os.listdir(self.mnt)


class filesystem_bpfs:
    _mount_overhead = 1 # the valid field
    def __init__(self, megabytes):
        self.img = tempfile.NamedTemporaryFile()
        # NOTE: self.mnt should not be in ~/ so that gvfs does not readdir it
        self.mnt = tempfile.mkdtemp()
        self.proc = None
        for i in range(megabytes * 64):
            self.img.write('0' * (16 * 1024))
    def __del__(self):
        if self.proc:
            self.unmount()
        os.rmdir(self.mnt)
    def format(self):
        subprocess.check_call(['./mkfs.bpfs', self.img.name], close_fds=True)
    def mount(self, pinfile=None):
        env = None
        if pinfile:
            env = os.environ
            env['PINOPTS'] = '-b true -o ' + pinfile
        self.proc = subprocess.Popen(['./bench/bpramcount',
                                      '-f', self.img.name, self.mnt],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      close_fds=True,
                                      env=env)
        while self.proc.stdout:
            line = self.proc.stdout.readline()
            if line == 'BPFS running\n':
                return
        raise NameError('Unable to start BPFS')
    def unmount(self):
        self.proc.terminate()
        output = self.proc.communicate()[0]
        self.proc = None
        for line in output.splitlines():
            if line.startswith('pin: ') and line.endswith(' bytes written to BPRAM'):
                return int(line.split()[1]) - self._mount_overhead
        raise NameError('BPFS failed to exit correctly')

class filesystem_kernel:
    def __init__(self, fs_name, img):
        self.fs_name = fs_name
        self.img = img
        # NOTE: self.mnt should not be in ~/ so that gvfs does not readdir it
        self.mnt = tempfile.mkdtemp()
        self.mounted = False
    def __del__(self):
        if self.mounted:
            self.unmount()
        os.rmdir(self.mnt)
    def format(self):
        cmd = ['sudo', 'mkfs.' + self.fs_name, self.img]
        if self.fs_name in ['ext2', 'ext3', 'ext4']:
            cmd.append('-q')
        subprocess.check_call(cmd, close_fds=True)
    def _get_dev_writes(self):
        dev_name = os.path.basename(self.img)
        file = open('/proc/diskstats', 'r')
        for line in file:
            fields = line.split()
            if fields[2] == dev_name:
                return int(fields[9]) * 512
        raise NameError('Device ' + dev_name + ' not found in /proc/diskstats')
    def mount(self, pinfile=None):
        subprocess.check_call(['sudo', 'mount', self.img, self.mnt],
                              close_fds=True)
        self.mounted = True
        subprocess.check_call(['sudo', 'chmod', '777', self.mnt],
                              close_fds=True)
        # Try to ignore the format and mount in write stats:
        subprocess.check_call(['sync'], close_fds=True)
        self.start_bytes = self._get_dev_writes()
    def unmount(self):
        # Catch all fs activity in write stats:
        subprocess.check_call(['sync'], close_fds=True)
        # Get write number before unmount to avoid including its activity
        stop_bytes = self._get_dev_writes()
        subprocess.check_call(['sudo', 'umount', self.mnt],
                              close_fds=True)
        self.mounted = False
        return stop_bytes - self.start_bytes

def run(fs, benches, profile):
    for name, clz in benches:
        pinfile = None
        if profile:
            pinfile = 'pin-' + name + '.log'
        sys.stdout.write('Benchmark ' + name + ': ')
        b = clz()
        b.mnt = fs.mnt
        fs.format()

        if hasattr(b, 'prepare'):
            fs.mount()
            b.prepare()
            fs.unmount()

        fs.mount(pinfile=pinfile)
        b.run()
        bytes = fs.unmount()

        sys.stdout.write(str(bytes) + ' bytes')
        if hasattr(b, 'opt'):
            delta = bytes - b.opt
            sys.stdout.write(' (' + str(delta))
            if b.opt:
                sys.stdout.write(' = ' + str(100 * delta / b.opt) + '%')
            sys.stdout.write(')')
        print ''
        if profile:
            subprocess.check_call(['./bench/parse_bpramcount'],
                                  stdin=open(pinfile))

def usage():
    print 'Usage: ' + sys.argv[0] + ' [-h|--help] [-t FS -d DEV] [-p] [BENCHMARK ...]'
    print '\t-t FS: use file system FS (e.g., bpfs or ext4)'
    print '\t-d DEV: use DEV for (non-bpfs) file system backing'
    print '\t-p: profile each run (bpfs only)'
    print '\tSpecifying no benchmarks runs all benchmarks'

def main():
    try:
        opts, bench_names = getopt.getopt(sys.argv[1:], 'hpt:d:', ['help'])
    except getopt.GetoptError, err:
        print str(err)
        sys.exit(1)
    profile = False
    benches = []
    fs_name = 'bpfs'
    dev = None
    fs = None
    for o, a in opts:
        if o == '-t':
            fs_name = a
        elif o == '-d':
            dev = a
        elif o == '-p':
            profile = True
        elif o in ('-h', '--help'):
            usage()
            sys.exit()
        else:
            assert False, 'unhandled option'

    if not bench_names:
        benches = benchmarks.all()
    else:
        bench_names = set(bench_names)
        for name, obj in inspect.getmembers(benchmarks):
            if inspect.isclass(obj) and name in bench_names:
                benches.append((name, obj))

    if fs_name == 'bpfs':
        fs = filesystem_bpfs(32)
    else:
        if dev == None:
            raise NameError('Must provide a backing device for ' + fs_name)
        fs = filesystem_kernel(fs_name, dev)

    run(fs, benches, profile)


if __name__ == '__main__':
    main()
