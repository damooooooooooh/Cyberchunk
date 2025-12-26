# Ingest OWASP Top 10 API Security Risks – 2023
# Run from project root: .\scripts\ingest_owasp_top10_API.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id="AI_Agent_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/AI_Agent_Security_Cheat_Sheet.md"},
    @{id="AJAX_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/AJAX_Security_Cheat_Sheet.md"},
    @{id="Abuse_Case_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Abuse_Case_Cheat_Sheet.md"},
    @{id="Access_Control_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Access_Control_Cheat_Sheet.md"},
    @{id="Attack_Surface_Analysis_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Attack_Surface_Analysis_Cheat_Sheet.md"},
    @{id="Authentication_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Authentication_Cheat_Sheet.md"},
    @{id="Authorization_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Authorization_Cheat_Sheet.md"},
    @{id="Authorization_Testing_Automation_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Authorization_Testing_Automation_Cheat_Sheet.md"},
    @{id="Automotive_Security"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Automotive_Security.md"},
    @{id="Bean_Validation_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Bean_Validation_Cheat_Sheet.md"},
    @{id="Browser_Extension_Vulnerabilities_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Browser_Extension_Vulnerabilities_Cheat_Sheet.md"},
    @{id="C-Based_Toolchain_Hardening_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/C-Based_Toolchain_Hardening_Cheat_Sheet.md"},
    @{id="CI_CD_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/CI_CD_Security_Cheat_Sheet.md"},
    @{id="Choosing_and_Using_Security_Questions_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Choosing_and_Using_Security_Questions_Cheat_Sheet.md"},
    @{id="Clickjacking_Defense_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Clickjacking_Defense_Cheat_Sheet.md"},
    @{id="Content_Security_Policy_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Content_Security_Policy_Cheat_Sheet.md"},
    @{id="Cookie_Theft_Mitigation_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Cookie_Theft_Mitigation_Cheat_Sheet.md"},
    @{id="Credential_Stuffing_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.md"},
    @{id="Cross-Site_Request_Forgery_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.md"},
    @{id="Cross_Site_Scripting_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.md"},
    @{id="Cryptographic_Storage_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Cryptographic_Storage_Cheat_Sheet.md"},
    @{id="DOM_Clobbering_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/DOM_Clobbering_Prevention_Cheat_Sheet.md"},
    @{id="DOM_based_XSS_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.md"},
    @{id="Database_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Database_Security_Cheat_Sheet.md"},
    @{id="Denial_of_Service_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Denial_of_Service_Cheat_Sheet.md"},
    @{id="Dependency_Graph_SBOM_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Dependency_Graph_SBOM_Cheat_Sheet.md"},
    @{id="Deserialization_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Deserialization_Cheat_Sheet.md"},
    @{id="Django_REST_Framework_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Django_REST_Framework_Cheat_Sheet.md"},
    @{id="Django_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Django_Security_Cheat_Sheet.md"},
    @{id="Docker_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Docker_Security_Cheat_Sheet.md"},
    @{id="DotNet_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/DotNet_Security_Cheat_Sheet.md"},
    @{id="Drone_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Drone_Security_Cheat_Sheet.md"},
    @{id="Error_Handling_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Error_Handling_Cheat_Sheet.md"},
    @{id="File_Upload_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/File_Upload_Cheat_Sheet.md"},
    @{id="Forgot_Password_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Forgot_Password_Cheat_Sheet.md"},
    @{id="GraphQL_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/GraphQL_Cheat_Sheet.md"},
    @{id="HTML5_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/HTML5_Security_Cheat_Sheet.md"},
    @{id="HTTP_Headers_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/HTTP_Headers_Cheat_Sheet.md"},
    @{id="HTTP_Strict_Transport_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/HTTP_Strict_Transport_Security_Cheat_Sheet.md"},
    @{id="Infrastructure_as_Code_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Infrastructure_as_Code_Security_Cheat_Sheet.md"},
    @{id="Injection_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Injection_Prevention_Cheat_Sheet.md"},
    @{id="Injection_Prevention_in_Java_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Injection_Prevention_in_Java_Cheat_Sheet.md"},
    @{id="Input_Validation_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Input_Validation_Cheat_Sheet.md"},
    @{id="Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.md"},
    @{id="JAAS_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/JAAS_Cheat_Sheet.md"},
    @{id="JSON_Web_Token_for_Java_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.md"},
    @{id="Java_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Java_Security_Cheat_Sheet.md"},
    @{id="Key_Management_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Key_Management_Cheat_Sheet.md"},
    @{id="Kubernetes_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Kubernetes_Security_Cheat_Sheet.md"},
    @{id="LDAP_Injection_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/LDAP_Injection_Prevention_Cheat_Sheet.md"},
    @{id="LLM_Prompt_Injection_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.md"},
    @{id="Laravel_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Laravel_Cheat_Sheet.md"},
    @{id="Legacy_Application_Management_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Legacy_Application_Management_Cheat_Sheet.md"},
    @{id="Logging_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Logging_Cheat_Sheet.md"},
    @{id="Logging_Vocabulary_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Logging_Vocabulary_Cheat_Sheet.md"},
    @{id="Mass_Assignment_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Mass_Assignment_Cheat_Sheet.md"},
    @{id="Microservices_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Microservices_Security_Cheat_Sheet.md"},
    @{id="Microservices_based_Security_Arch_Doc_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Microservices_based_Security_Arch_Doc_Cheat_Sheet.md"},
    @{id="Mobile_Application_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Mobile_Application_Security_Cheat_Sheet.md"},
    @{id="Multifactor_Authentication_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Multifactor_Authentication_Cheat_Sheet.md"},
    @{id="NPM_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/NPM_Security_Cheat_Sheet.md"},
    @{id="Network_Segmentation_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Network_Segmentation_Cheat_Sheet.md"},
    @{id="NoSQL_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/NoSQL_Security_Cheat_Sheet.md"},
    @{id="NodeJS_Docker_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/NodeJS_Docker_Cheat_Sheet.md"},
    @{id="Nodejs_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Nodejs_Security_Cheat_Sheet.md"},
    @{id="OAuth2_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/OAuth2_Cheat_Sheet.md"},
    @{id="OS_Command_Injection_Defense_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.md"},
    @{id="PHP_Configuration_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/PHP_Configuration_Cheat_Sheet.md"},
    @{id="Password_Storage_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Password_Storage_Cheat_Sheet.md"},
    @{id="Pinning_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Pinning_Cheat_Sheet.md"},
    @{id="Prototype_Pollution_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Prototype_Pollution_Prevention_Cheat_Sheet.md"},
    @{id="Query_Parameterization_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Query_Parameterization_Cheat_Sheet.md"},
    @{id="REST_Assessment_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/REST_Assessment_Cheat_Sheet.md"},
    @{id="REST_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/REST_Security_Cheat_Sheet.md"},
    @{id="Ruby_on_Rails_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Ruby_on_Rails_Cheat_Sheet.md"},
    @{id="SAML_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/SAML_Security_Cheat_Sheet.md"},
    @{id="SQL_Injection_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.md"},
    @{id="Secrets_Management_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Secrets_Management_Cheat_Sheet.md"},
    @{id="Secure_AI_Model_Ops_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Secure_AI_Model_Ops_Cheat_Sheet.md"},
    @{id="Secure_Cloud_Architecture_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Secure_Cloud_Architecture_Cheat_Sheet.md"},
    @{id="Secure_Code_Review_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Secure_Code_Review_Cheat_Sheet.md"},
    @{id="Secure_Product_Design_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Secure_Product_Design_Cheat_Sheet.md"},
    @{id="Securing_Cascading_Style_Sheets_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Securing_Cascading_Style_Sheets_Cheat_Sheet.md"},
    @{id="Server_Side_Request_Forgery_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.md"},
    @{id="Serverless_FaaS_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Serverless_FaaS_Security_Cheat_Sheet.md"},
    @{id="Session_Management_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Session_Management_Cheat_Sheet.md"},
    @{id="Software_Supply_Chain_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.md"},
    @{id="Symfony_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Symfony_Cheat_Sheet.md"},
    @{id="TLS_Cipher_String_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/TLS_Cipher_String_Cheat_Sheet.md"},
    @{id="Third_Party_Javascript_Management_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Third_Party_Javascript_Management_Cheat_Sheet.md"},
    @{id="Third_Party_Payment_Gateway_Integration"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Third_Party_Payment_Gateway_Integration.md"},
    @{id="Threat_Modeling_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Threat_Modeling_Cheat_Sheet.md"},
    @{id="Transaction_Authorization_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Transaction_Authorization_Cheat_Sheet.md"},
    @{id="Transport_Layer_Protection_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Transport_Layer_Protection_Cheat_Sheet.md"},
    @{id="Transport_Layer_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Transport_Layer_Security_Cheat_Sheet.md"},
    @{id="Unvalidated_Redirects_and_Forwards_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.md"},
    @{id="User_Privacy_Protection_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/User_Privacy_Protection_Cheat_Sheet.md"},
    @{id="Virtual_Patching_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Virtual_Patching_Cheat_Sheet.md"},
    @{id="Vulnerability_Disclosure_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Vulnerability_Disclosure_Cheat_Sheet.md"},
    @{id="Vulnerable_Dependency_Management_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Vulnerable_Dependency_Management_Cheat_Sheet.md"},
    @{id="WebSocket_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/WebSocket_Security_Cheat_Sheet.md"},
    @{id="Web_Service_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Web_Service_Security_Cheat_Sheet.md"},
    @{id="XML_External_Entity_Prevention_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.md"},
    @{id="XML_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/XML_Security_Cheat_Sheet.md"},
    @{id="XSS_Filter_Evasion_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/XSS_Filter_Evasion_Cheat_Sheet.md"},
    @{id="XS_Leaks_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/XS_Leaks_Cheat_Sheet.md"},
    @{id="Zero_Trust_Architecture_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Zero_Trust_Architecture_Cheat_Sheet.md"},
    @{id="gRPC_Security_Cheat_Sheet"; url="https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/gRPC_Security_Cheat_Sheet.md"}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Cheatsheets Series ($($sources.Count) items)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$success = 0
$failed  = 0

foreach ($source in $sources) {
    Write-Host "`n--- Processing $($source.id) ---" -ForegroundColor Yellow

    # Build args as an array (no escaping hell, no Invoke-Expression)
    $args = @(
        "-m", "rag_builder.cli", "ingest",
        "--publisher", "OWASP",
        "--collection", "OWASP Cheatsheets",
        "--document-name", "OWASP Cheatsheets",
        "--edition", "2025",
        "--dataset-id", "owasp_cheatsheets",
        "--version", "2025",
        "--use-llm",
        "--enrich-tags",
        "--use-postgres",
        "--preserve-source",
        "--source", $source.url,
        "--item-id", $source.id
    )

    Write-Host ("Running: python " + ($args -join " ")) -ForegroundColor Gray

    try {
        & python @args
        $exit = $LASTEXITCODE

        if ($exit -eq 0) {
            $success++
            Write-Host "`n✓ Success: $($source.id)" -ForegroundColor Green
        }
        else {
            $failed++
            Write-Host "`n✗ Failed: $($source.id) (exit code: $exit)" -ForegroundColor Red
        }
    }
    catch {
        $failed++
        Write-Host "`n✗ Error: $($source.id) - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingestion Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✓ Successful: $success" -ForegroundColor Green
Write-Host "✗ Failed: $failed" -ForegroundColor Red
Write-Host "`nNext step: python -m rag_builder.cli embed --provider ollama --batch-size 50`n" -ForegroundColor Yellow
