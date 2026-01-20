CREATE MASKING POLICY mask_lbl_auth_secret maskall ON LABEL(lbl_auth_secret) FILTER ON ROLES(analytics_user);
CREATE MASKING POLICY mask_lbl_pii_raw maskall ON LABEL(lbl_pii_raw) FILTER ON ROLES(analytics_user);
CREATE MASKING POLICY mask_lbl_pii_low maskall ON LABEL(lbl_pii_low) FILTER ON ROLES(analytics_user);
CREATE MASKING POLICY mask_lbl_pci maskall ON LABEL(lbl_pci) FILTER ON ROLES(analytics_user);
CREATE MASKING POLICY mask_lbl_free_text_pii maskall ON LABEL(lbl_free_text_pii) FILTER ON ROLES(analytics_user);