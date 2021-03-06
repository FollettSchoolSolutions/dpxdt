#!/bin/bash
run_results="/usr/local/dpxdt/capture/runresults.txt"
deploypath="/usr/local/dpxdt/deployment"
configure_hostname() {
   #Allow 2nd parameter and 3rd to specify the hostname & port, e.g., localhost 5000, 172.x.x.x 3000, myhost 6000, etc
  if [ ! -z "$2" ]; then
    hostname=$2
  else
    hostname=localhost
  fi
  if [ ! -z "$3" ]; then
    port=$3
  else
    port=5000
  fi
  sed -i "s/<HOST>/${hostname}/g" $deploypath/mysql/flags.cfg
  sed -i "s/<PORT>/${port}/g"     $deploypath/mysql/flags.cfg

  sed -i "s/<HOST>/${hostname}/g" $deploypath/sqlite/flags.cfg
  sed -i "s/<PORT>/${port}/g"     $deploypath/sqlite/flags.cfg

  #Dpxdt is a linked directory, we only have to update this once and all deployments will get the value
  sed -i "s/<HOST>/$hostname/g"     $deploypath/mysql/dpxdt/server/config.py 
  sed -i "s/<PORT>/$port/g"         $deploypath/mysql/dpxdt/server/config.py 

}
if [ "$1" = 'capture' ]; then
  # Make sure 2nd argument exists
  if [ ! -z "$2" ]; then
    cd /usr/local/dpxdt
    pip install -e .
    source capture/"$2".properties
   
    ./dpxdt/tools/fss_diff_url.py --upload_build_id=$upload_build_id --release_server_prefix=$release_server_prefix --release_client_id=$release_client_id --release_client_secret=$release_client_secret --release_cut_url=$release_cut_url --tests_json_path="/usr/local/dpxdt/capture/$2.json" --upload_release_name=$upload_release_name > $run_results
    cat $run_results 
    if [ "$3" = "wait" ]; then
      /usr/local/dpxdt/waitforjob.sh $run_results 
    fi  

  else
    echo "You must supply the name of the properties file after the 'capture' parameter, i.e., for 'mytest.properties', specify 'mytest'"
  fi      
elif [ "$1" = 'start' ]; then
   configure_hostname $@ 
   make mysql_deploy
   cd mysql_deploy
   virtualenv .
   ./run.sh
   #exec ./run_combined.sh $@ 
elif [ "$1" = 'start_db_exists' ]; then
   make mysql_exists_deploy
   cd mysql_deploy
   virtualenv .
   ./run.sh
elif [ "$1" = 'start_sqlite' ]; then
   configure_hostname $@ 
   make sqlite_deploy
   cd sqlite_deploy
   virtualenv .
   ./run.sh
else 
   echo Additional options: start, capture, start_db_exists, start_sqlite
   echo If capture, then you will need to mount a folder to the /usr/dpxdt/capture directory, as follows:
   echo docker run -v /home/asg/depictedChanges/capture:/usr/local/dpxdt/capture fss/dpxdt capture testname wait
   echo 
   echo start is the option to use if you are starting from scratch with an empty mysql instance.  The container will expect you to have
   echo have a linked mysql container named dpxdt_db with an empty db named dpxdt and a user named dpxdt with password of 'password'.
   echo You may also pass in host and port, e.g., start 172.x.x.x 5000 
   echo start_db_exists is for starting an instance with a pre-existing MySql database -- no changes will be made to the database
   echo on startup.
   echo start_sqlite will start a self contained clean instance of dpxdt, and all storage will remain with the container
   
fi
