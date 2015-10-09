#!/bin/bash
if [ "$1" = 'capture' ]; then
      
   cd /usr/local/dpxdt
   pip install -e .
   source capture/test.properties
   
   exec ./dpxdt/tools/fss_diff_url.py --upload_build_id=$upload_build_id --release_server_prefix=$release_server_prefix --release_client_id=$release_client_id --release_client_secret=$release_client_secret --release_cut_url=$release_cut_url --tests_json_path=$tests_json_path --upload_release_name=$upload_release_name

elif [ "$1" = 'start' ]; then
   make mysql_deploy
   cd mysql_deploy
   virtualenv .
   ./run.sh
   #exec ./run_combined.sh $@ 
elif [ "$1" = 'start_sqlite' ]; then
   make sqlite_deploy
   cd sqlite_deploy
   virtualenv .
   ./run.sh
else 
   echo Additional options: start, capture
   echo When start is used, you may optionally add these --ignore_auth, --verbose_workers=true, --verbose_queries=true
   echo If capture, then you will need to mount a folder to the /usr/dpxdt/capture directory, as follows:
   echo docker run -v /home/asg/depictedChanges/capture:/usr/local/dpxdt/capture fss/dpxdt capture
fi
