.. _module_view:

Module View
============

.. note::
   The current module view is a work in progress and will be updated as the
   project evolves and when a final structure is established and agreed upon.


High Level Overview
----------------------

The module view in the OSO Services offers a high-level overview of the system's core components and their primary interactions. To support deeper understanding, 
dedicated module views are provided for both the OSD Mapper and the Proposal Handling Tool (PHT).


.. figure:: diagrams/module_top_view.svg
   :width: 800
   :align: center
   :alt: Module View Diagram of the oso-services

   High level module view diagram of the oso-services


OSD Mapper Module
--------------------

The OSD mapper module includes three core functions: configuration_from_osd, which returns a general Configuration object, and two helper functions—_get_mid_telescope_configuration and _get_low_telescope_configuration, 
which return specialized configurations for mid and low telescope setups, respectively.

.. figure:: diagrams/module_view_osd.svg
   :width: 800
   :align: center
   :alt: Module View Diagram of the OSD mapper

   Module View Diagram of the OSD mapper


PHT Module
---------------------

The PHT module view highlights the internal structure and interactions related to proposal preparation (PPT) and proposal management (PMT), 
offering insight into how these components collaborate to support the end-to-end proposal lifecycle.

.. figure:: diagrams/module_view_pht.svg
   :width: 800
   :align: center
   :alt: Module View Diagram of the PHT

   Module View Diagram of the PHT