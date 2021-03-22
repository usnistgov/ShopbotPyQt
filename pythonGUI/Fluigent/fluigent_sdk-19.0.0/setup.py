from setuptools import setup, find_packages
import os
import tarfile

from Fluigent.SDK import __version__

sharedObjectVersion = "1.0.0"

for root, dirs, files in os.walk("Fluigent"):
    for file in files:
        if file.endswith(".tar.gz"):
            with tarfile.open(os.path.join(root, file)) as tar:
                res = [tar.extract(f, root) for f in tar if f.isreg()]

setup(name="fluigent_sdk",
      version=__version__,
      description="SDK for Fluigent Instruments",
      url="http://www.fluigent.com",
      author="Fluigent",
      author_email="support@fluigent.com",
      license="Proprietary",
      packages=find_packages(exclude=("tests",)),
      namespace_packages=["Fluigent"],
      package_data={"Fluigent.SDK": ["shared/windows/*.dll",
                                        "shared/linux/*.so."+sharedObjectVersion,
                                        "shared/pi/*.so."+sharedObjectVersion]},
      zip_safe=False)
