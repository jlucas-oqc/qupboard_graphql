#!/usr/bin/env python3
import subprocess
from pathlib import Path
from junitparser import JUnitXml


def parse_junit(xml_path):
    xml = JUnitXml.fromfile(str(xml_path))
    summary = {
        "tests": xml.tests,
        "failures": xml.failures,
        "errors": xml.errors,
        "skipped": xml.skipped,
    }
    return summary


def pycobertura_markdown(coverage_xml):
    try:
        result = subprocess.run(
            ["poetry", "run", "pycobertura", "show", str(coverage_xml), "--format", "markdown"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Failed to generate coverage table for {coverage_xml}: {e.stderr}"


def main():
    report_dir = Path("reports")
    junit_files = sorted(report_dir.glob("junit-*.xml"))
    print("# Test Results and Coverage\n")
    for junit in junit_files:
        pyver = junit.stem.split("-")[-1]
        print(f"## Python {pyver}\n")
        summary = parse_junit(junit)
        print(f"**Tests:** {summary['tests']}  ")
        print(f"**Failures:** {summary['failures']}  ")
        print(f"**Errors:** {summary['errors']}  ")
        print(f"**Skipped:** {summary['skipped']}\n")
        cov_xml = report_dir / f"coverage-{pyver}.xml"
        if cov_xml.exists():
            print(pycobertura_markdown(cov_xml))
        else:
            print("No coverage report found.\n")


if __name__ == "__main__":
    main()
