# Running gently

Recovery reads gigabytes and runs for hours, often on old machines with tired disks. An early
version froze a PC with a failing system SSD: a diagnostic kept 2 MB lookup tables for
thousands of camera table sets in every worker, ran out of RAM, and the OS paged heavily to
the failing disk. PhotoPhoenix now:

- **Small, bounded lookup tables:** 9-bit first-level Huffman tables (~4 KB instead of ~2 MB)
  in an LRU cache capped at 256 entries. Touching all ~9,000 table sets adds ~1 MB.
- **Caps workers:** 4 by default, 6 at most; ~200 MB RAM each.
- **Low priority (Windows):** workers run at idle CPU, very-low disk I/O and low memory
  priority; the window at below-normal CPU and low disk priority. (Declaring ctypes argument
  types matters: without them the 64-bit process handle is truncated and the call silently
  does nothing.) On other systems: `nice`.
- **RAM guard:** no new photo starts while free RAM is below `min_free_ram_gb` (3 GB).
- **Fewer writes:** progress is saved every 25 photos, atomically.
- **Temp files** go to `temp_dir`, which you can put on a healthy disk.
- **Scope:** only configured folders are read; nothing outside them is scanned.

Tip: if your system disk is failing, also move the OS page file to a healthy disk.
