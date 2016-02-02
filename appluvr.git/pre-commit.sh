#Author: Arvi

# Stash away changes to avoid running tests on files that arent being commited anyways
git stash -q

# Run through unit tests
(cd workers && python test_build_carousel_views.py)
RESULT=$?

# Quietly pop stash
git stash pop -q

# If alls good with the result go ahead with commit
# and if not, bail out
echo $RESULT
[ $RESULT -ne 0 ] && exit 1
exit 0
