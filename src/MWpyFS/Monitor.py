# The monitor is used to monitor the FS fragmentation status.
# What I want to see is, generally, how's the metadata. This may include:
#
#  SIZE of inode and extent tree. (number of inode block and extent tree
#  block). This can be find by debugfs "dump_extents [-n] [-l] filespec".
#  But you have to do it for ALL files in the file system, which might be
#  slow. I haven't got a better approach. A good indicator of metadata
#  problem is #_metadata_block/#_data_block. This should be very informative
#  about the aging of a file system which causes metadata disaster.
#       I expect the following from the output of this per file:
#       
#       filepath create_time n_metablock n_datablock metadata_ratio filebytes
#
#  Extent fragmentation overview. This can be obtained by e2freefrag. This
#  should give me a good sense of how fragemented the FS is. The acceleration
#  rate of fragmentation might be a good indicator of whether a workload
#  can cause metadata problem. (Because of fragmentation, physical blocks
#  might not be able to allocated contiguously, then it needs two or more
#  extents to the logically contiguous blocks.)
#       I expect the following from the output of this per FS:
#       JUST LIKE THE ORIGINAL OUTPUT BUT FORMAT IT A LITTLE BIT

import subprocess
from time import gmtime, strftime
import re
import shlex
import os.path

def dict2table(mydict):
    mytable = ""
    for keyname in mydict:
        mystr = " ".join( [keyname, mydict[keyname]] )
        mytable += mystr + "\n"
    return mytable
        

class FSMonitor:
    """
    This monitor probes the ext4 file system and return information I 
    want in a nice format.
    """
    def __init__(self, dn, mp):
        self.devname = dn 
        self.mountpoint = mp # please only provide path without mountpoint
                             # when using this class.
        self.monitor_id = strftime("%Y-%m-%d-%H-%M-%S", gmtime())
    
    def e2freefrag(self):
        cmd = ["e2freefrag", self.devname]
        proc = subprocess.Popen(cmd,
                           stdout=subprocess.PIPE)
        proc.wait()

        part = 0
        sums_dict = {}
        hist_table = ""
        for line in proc.stdout:
            if part == 0:
                if "HISTOGRAM" in line:
                    part = 1
                    continue
                mo = re.search( r'(.*): (\d+)', line, re.M)
                if mo:
                    keyname = mo.group(1)
                    keyname = keyname.replace('.', '')
                    keyname = "_".join(keyname.split())
                    sums_dict[keyname] = mo.group(2)
            elif part == 1:
                # This part is the histogram.
                if "Extent Size" in line:
                    hist_table = "Extent_start Extent_end  Free_extents   Free_Blocks  Percent\n"
                    continue
                fline = re.sub(r'[\-:\n]', "", line)
                fline = re.sub(r'\.{3}', "", fline)
                hist_table += fline + "\n"
                 
        return (dict2table(sums_dict), hist_table)

        
    def dump_extents(self, filepath):
        cmd = "debugfs /dev/sdb1 -R 'dump_extents " + filepath + "'"
        cmd = shlex.split(cmd)
        print cmd
        proc = subprocess.Popen(cmd, stdout = subprocess.PIPE)
        proc.wait()

        ext_list = [] # Use list here in case I want to extract data in Python
        header = []
        n_entries = [0] * 3 # n_entries[k] is the number of entries at level k
                            # it can be used to calculate number of 
                            # internal/leaf nodes
        max_level = 0
        for line in proc.stdout:
            print "LLL:", line,
            if "Level" in line:
                header = ["Level_index", "Max_level", 
                         "Entry_index", "N_Entry",
                         "Logical_start", "Logical_end",
                         "Physical_start", "Physical_end",
                         "Length", "Flag"]
            else:
                line = re.sub(r'[/\-]', "", line)
                tokens = line.split()
                d = {}
                for i in range(9):
                    d[ header[i] ] = tokens[i]
                
                if len(tokens) == 10:
                    d["Flag"] = tokens[10]
                else:
                    d["Flag"] = "NA"

                n_entries[ int(d["Level_index"]) ] = int( d["N_Entry"] )
                max_level = int( d["Max_level"] )
                
        # calculate number of meatadata blocks
        # only 1st and 2nd levels takes space. 
        # How to calculate:
        #   if there is only 1 level (root and level 1).
        #   the number of entires in level 0 indicates the
        #   number of nodes in level 1.
        #   Basically, the number of entries in level i
        #   equals the number of ETB of the next level
        n_metablock = 0
        if max_level == 0:
            # the tree has no extent tree block outside of the inode
            n_metablock = 0
        else:
            for n in n_entries[0:max_level]:
                n_metablock += n
        
        dumpdict = {}
        dumpdict["filepath"] = filepath
        dumpdict["n_metablock"] = n_metablock
        others = self.filefrag(filepath)
        dumpdict["n_datablock"] = others["nblocks"]
        dumpdict["filebytes"] = others["nbytes"]
    
        return dumpdict

#    def ls(self, filepath):
        #fullpath = os.path.join(self.mountpoint, filepath)  
        #cmd = ["ls", "-ls", fullpath]
        #proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        #proc.wait()

        #lines = proc.stdout.readlines()
        #if len(lines) != 1:
            #print "I expect only one line"
            #exit(1)
        #line = lines[0]
        #print line.split() 
            
    def filefrag(self, filepath):
        fullpath = os.path.join(self.mountpoint, filepath)  
        cmd = ["filefrag", "-sv", fullpath]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc.wait()

        mydict = {}
        for line in proc.stdout:
            if line.startswith("File size of"):
                print line
                line = line.split(" is ")[1]
                print line
                nums = re.findall(r'\d+', line)
                if len(nums) != 3:
                    print "filefrag something wrong"
                    exit(1)
                mydict["nbytes"] = nums[0]
                mydict["nblocks"] = nums[1]
                mydict["blocksize"] = nums[2]
        return mydict

fsmon = FSMonitor("/dev/sdb1", "/mnt/scratch")
#frag = fsmon.e2freefrag()
print fsmon.dump_extents("myfirstfile")
#fsmon.ls("filesss")
#print fsmon.filefrag("filesss")





