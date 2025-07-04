.. _prsl:

Create Proposal 
===================

Sequence diagram function flow when calling create proposal endpoint /prsls/create

.. image:: diagrams/create_proposal_api.svg
   :width: 400
   :alt: Sequence diagram for create proposal API

Retrieve Proposals 
===================
Sequence diagram function flow when calling retrieve proposal endpoint /prsls/{proposal_id}

.. image:: diagrams/get_proposal_api.svg
  :width: 400
  :alt: Sequence diagram for retrieve proposal API

Edit Proposal
===============
Sequence diagram function flow when calling edit proposal endpoint /prsls/{proposal_id}

.. image:: diagrams/edit_proposal_api.svg
  :width: 400
  :alt: Sequence diagram for edit proposal API  

Retrieve list of Proposals 
===========================
Sequence diagram function flow when calling get list of proposals endpoint /prsls/list/{user_id}

.. image:: diagrams/get_list_of_proposals_by_user_id_api.svg
  :width: 400
  :alt: Sequence diagram for get list of proposals by user id API  

Validate Proposal
==================
Sequence diagram function flow when calling validate proposal endpoint /prsls/validate

.. image:: diagrams/validate_proposal_api.svg
  :width: 400
  :alt: Sequence diagram for validate proposal API  

Email invite
=============
Sequence diagram function flow when calling email invite endpoint /prsls/send-email

.. image:: diagrams/send_email_api.svg
  :width: 400
  :alt: Sequence diagram for email invite API  

Generate presigned S3 upload URL
=================================
Sequence diagram function flow when calling email invite endpoint /prsls/signed-url/upload/{filename}

.. image:: diagrams/upload_pdf_api.svg
  :width: 400
  :alt: Sequence diagram for generate presigned S3 upload URL API  

Generate presigned S3 download URL
===================================
Sequence diagram function flow when calling email invite endpoint /prsls/signed-url/download/{filename}

.. image:: diagrams/download_pdf_api.svg
  :width: 400
  :alt: Sequence diagram for generate presigned S3 download URL API 

Generate presigned S3 delete URL
=================================
Sequence diagram function flow when calling email invite endpoint /prsls/signed-url/delete/{filename}

.. image:: diagrams/delete_pdf_api.svg
  :width: 400
  :alt: Sequence diagram for generate presigned S3 delete URL API 