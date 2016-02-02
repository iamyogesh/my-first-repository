BASE=$(dirname $0)
ENV=$BASE/env

test ! -d $ENV && virtualenv --distribute --no-site-packages $ENV
pip install -E $ENV -r $BASE/requirements.txt

echo "== Bootstrap finished, use env/bin/activate to get started"
