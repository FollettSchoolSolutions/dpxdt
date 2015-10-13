#!/bin/bash
#Usage: ./waitforjob.sh output.txt, where output.txt is the output from one of the capture utilities, that should contain within
#its output the URL for the given job.  The given job should be publicly accessible in order for this script to work.
#This will poll the given release run page until the status changes to 'Reviewing'.
#After this it will do a simple grep on the page for the word failure to determine if there were any differences someone should be 
#notified about.  The return status of this script will then return 0 for success (no differences) or nonzero for failure (some differences found)
url=$(cat $1 | grep -o -e 'http:.*')
iteration=0
iteration_limit=60
delay=60
echo "Using URL: $url"
review_status=""

#Once it is in reviewing status, we can check for word failure.  if found, we fail build. else, it passes
#do until we found the Status: Reviewing text or until we exceed the number of iterations
while [ -z "$review_status" ] && [ $iteration -lt $iteration_limit ]; do
    sleep $delay
    review_status=$(curl "$url"  | grep -o -E "Status: (Bad|Good|Reviewing)")
    iteration=$[$iteration + 1]
    echo "Iteration $iteration, checking again"
done

#Check to make sure we didn't timeout
if [ $iteration -ge $iteration_limit ]; then
    echo "Timed out waiting for the job to finish, exiting with failure code"
    exit 2
fi

fail_status=$(curl "$url" | grep failure)
echo "Fail status: $fail_status"
#If the word failure is found on the page, then we consider this run a failure, and set the status code accordingly
if [ ! -z "$fail_status" ]; then
    exit 1
else
    exit 0
fi

