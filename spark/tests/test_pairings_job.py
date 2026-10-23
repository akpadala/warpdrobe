import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import make_sample_data  # noqa: E402
import pairings_job  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    s = (SparkSession.builder.master("local[2]").appName("test")
         .config("spark.sql.shuffle.partitions", "4").config("spark.ui.enabled", "false").getOrCreate())
    yield s
    s.stop()


def test_article_mapping(spark, tmp_path):
    data = make_sample_data.write(tmp_path / "data")
    arts = spark.read.csv(str(data / "articles.csv"), header=True)
    rows = {r["article_id"]: (r["category"], r["color"]) for r in pairings_job.article_tokens(arts).collect()}
    assert rows[1] == ("top", "white")
    assert rows[3] == ("bottom", "blue")
    assert rows[4] == ("bottom", "navy")         # Dark Blue -> navy
    assert rows[7] == ("outerwear", "beige")     # coats aren't tops
    assert rows[8] == ("dress", "multi")         # all-over print
    assert 9 not in rows and 10 not in rows      # underwear and kids dropped


def test_job_end_to_end(spark, tmp_path):
    data = make_sample_data.write(tmp_path / "data")
    out = tmp_path / "pairings.json"
    res = pairings_job.run(data, out, min_baskets=3, spark=spark)
    saved = json.loads(out.read_text())
    assert saved["meta"]["source"] == "hm" and saved["meta"]["baskets"] > 0
    pairs = saved["pairs"]
    # Strong synthetic patterns come out with lift > 1.
    assert pairs["bottom|blue::top|white"] > 1
    assert pairs["bottom|black::top|black"] > 1
    assert pairs["bottom|blue::shoes|white"] > 1
    # Keys are sorted token pairs, matching backend/app/pairings.py.
    assert all(k.split("::")[0] < k.split("::")[1] for k in pairs)
    # Same-category pairs (two tops) are never counted as outfits.
    assert not any(k.split("::")[0].split("|")[0] == k.split("::")[1].split("|")[0] for k in pairs)
    assert all(n >= 3 for n in saved["support"].values())
    assert "black::black" in saved["color_pairs"]
    assert res["meta"]["pairs"] == len(pairs)


def test_min_support_filters_rare_pairs(spark, tmp_path):
    data = make_sample_data.write(tmp_path / "data")
    res = pairings_job.run(data, tmp_path / "p.json", min_baskets=10**6, spark=spark)
    assert res["pairs"] == {}


BACKEND = Path(__file__).resolve().parents[2] / "backend"


@pytest.mark.skipif(not (BACKEND / ".venv" / "bin" / "python").exists(), reason="backend venv not set up")
def test_backend_reads_job_output(spark, tmp_path):
    """The API (separate environment) loads the job's JSON and prefers it over the color rules."""
    data = make_sample_data.write(tmp_path / "data")
    out = tmp_path / "pairings.json"
    pairings_job.run(data, out, min_baskets=3, spark=spark)
    code = (
        "from pathlib import Path; from app.pairings import PairingModel as P; import sys;"
        f"m = P.load(Path({str(out)!r})); assert m.meta['source'] == 'hm';"
        "assert m.score('top','white','bottom','blue') > P().score('top','white','bottom','blue')"
    )
    subprocess.run([str(BACKEND / ".venv" / "bin" / "python"), "-c", code], cwd=BACKEND, check=True,
                   env={**os.environ, "PYTHONPATH": str(BACKEND)})


def test_holdout_split(spark, tmp_path):
    data = make_sample_data.write(tmp_path / "data")
    res = pairings_job.run(data, tmp_path / "pairings.json", min_baskets=2, spark=spark,
                           holdout_from="2020-03-01")
    hold = json.loads((tmp_path / "holdout_baskets.json").read_text())["baskets"]
    assert res["meta"]["holdout_baskets"] == len(hold) > 0
    assert all(len(b) >= 2 for b in hold)
