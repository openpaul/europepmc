cat metagenomicids.txt | awk '{print "python3 main.py",$2,$1, "meta_"$2,"; python3 main.py",$2,$1, "meta_"$2," -f 1"} ' 
