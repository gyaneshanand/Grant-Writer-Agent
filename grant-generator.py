# This file orchestrates the complete grant processing pipeline:
# 1. Grant Data Collector -> Fetches grants in JSON format
# 2. Organization Data Collector -> Fetches organization info in JSON format  
# 3. Grant Writer -> Generates consolidated grant opportunity description
# 4. Grant Metadata Writer -> Generates 6 metadata fields for Grant Details Page

# Final Output: Consolidated JSON with grant description and metadata

import json
import sys
import os
import importlib.util

# Import grant data collector
def load_grant_collector():
    try:
        spec = importlib.util.spec_from_file_location("grant_data_collector", "grant-data-collector.py")
        grant_collector_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(grant_collector_module)
        return grant_collector_module
    except Exception as e:
        print(f"❌ Error loading grant data collector: {e}")
        return None

# Import organization data collector
def load_organization_collector():
    try:
        spec = importlib.util.spec_from_file_location("organization_data_collector", "organisation-data-collector.py")
        org_collector_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(org_collector_module)
        return org_collector_module
    except Exception as e:
        print(f"❌ Error loading organization data collector: {e}")
        return None

# Import grant writer  
def load_grant_writer():
    try:
        spec = importlib.util.spec_from_file_location("grant_writer", "grant-writer.py")
        grant_writer_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(grant_writer_module)
        return grant_writer_module.GrantWriter
    except Exception as e:
        print(f"❌ Error loading grant writer: {e}")
        return None

# Import grant metadata writer
def load_grant_metadata_writer():
    try:
        spec = importlib.util.spec_from_file_location("grant_metadata_writer", "grant-metadata-writer.py")
        metadata_writer_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metadata_writer_module)
        return metadata_writer_module.GrantMetadataWriter
    except Exception as e:
        print(f"❌ Error loading grant metadata writer: {e}")
        return None


def main():
    print("🚀 Grant Generator - Complete Pipeline")
    print("=" * 60)
    print("Step 1: Grant Data Collector")
    print("Step 2: Organization Data Collector") 
    print("Step 3: Grant Writer")
    print("Step 4: Grant Metadata Writer")
    print("=" * 60)
    
    # Load all required modules
    print("📦 Loading modules...")
    grant_collector = load_grant_collector()
    org_collector = load_organization_collector()
    GrantWriter = load_grant_writer()
    GrantMetadataWriter = load_grant_metadata_writer()
    
    if not all([grant_collector, org_collector, GrantWriter, GrantMetadataWriter]):
        print("❌ Failed to load required modules")
        return
    
    print("✅ All modules loaded successfully")
    
    # Configuration
    FOUNDATION_URL = "https://momenifoundation.org/"  # Change this URL as needed
    OPENAI_API_KEY = "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"
    
    # STEP 1: Fetch grants in JSON format
    print(f"\n🔍 STEP 1: Fetching grants from {FOUNDATION_URL}")
    print("-" * 50)
    
    try:
        grants = grant_collector.run_pipeline(FOUNDATION_URL)
        print(f"✅ Successfully fetched {len(grants)} grants")
        
        if not grants:
            print("❌ No grants found")
            return
            
    except Exception as e:
        print(f"❌ Error fetching grants: {e}")
        return
    
    # STEP 2: Fetch organization data
    print(f"\n🏢 STEP 2: Fetching organization data from {FOUNDATION_URL}")
    print("-" * 50)
    
    org_data = None
    try:
        org_data = org_collector.collect_organization_data(FOUNDATION_URL)
        if org_data:
            print(f"✅ Successfully fetched organization data for: {org_data.get('org_name', 'Unknown Org')}")
        else:
            print("⚠️ No organization data found - proceeding without org context")
    except Exception as e:
        print(f"⚠️ Error fetching organization data: {e}")
        print("📝 Proceeding without organization context")
        org_data = None
    
    # STEP 3: Generate consolidated grant opportunity description
    print(f"\n📝 STEP 3: Generating consolidated grant description from {len(grants)} grants...")
    print("-" * 50)
    
    try:
        writer = GrantWriter(OPENAI_API_KEY)
        
        # Use organization data if available
        consolidated_result = writer.process_grants_consolidated(grants, org_data)
        
        print(f"✅ Consolidated description generated successfully!")
        print(f"📊 Total grants consolidated: {consolidated_result['grant_count']}")
        print(f"🎯 Grant programs: {', '.join(consolidated_result['grant_names'])}")
        
        grant_description = consolidated_result['description']
        
    except Exception as e:
        print(f"❌ Error generating consolidated description: {e}")
        return
    
    # STEP 4: Generate grant metadata (6 fields)
    print(f"\n🏷️ STEP 4: Generating grant metadata (6 fields)...")
    print("-" * 50)
    
    try:
        metadata_writer = GrantMetadataWriter(OPENAI_API_KEY)
        
        # Generate metadata from the consolidated description
        grant_metadata = metadata_writer.process_grant_opportunity_metadata(grant_description)
        
        if grant_metadata:
            print(f"✅ Grant metadata generated successfully!")
            print(f"📊 Generated fields: {', '.join(grant_metadata.keys())}")
        else:
            print("❌ Failed to generate grant metadata")
            return
            
    except Exception as e:
        print(f"❌ Error generating grant metadata: {e}")
        return
    
    # FINAL OUTPUT: Create consolidated JSON result
    print(f"\n🎯 CREATING CONSOLIDATED JSON RESULT")
    print("=" * 60)
    
    final_result = {
        "pipeline_info": {
            "foundation_url": FOUNDATION_URL,
            "grants_processed": len(grants),
            "organization_data_available": org_data is not None,
            "processing_date": "2025-09-28"
        },
        "grant_opportunity_description": grant_description,
        "grant_metadata": grant_metadata,
        "source_data": {
            "grants_count": len(grants),
            "grant_names": consolidated_result['grant_names'],
            "source_urls": consolidated_result.get('source_urls', []),
            "organization_name": org_data.get('org_name') if org_data else None
        }
    }
    
    # Display final result summary
    print(f"📄 FINAL CONSOLIDATED RESULT:")
    print(f"🏢 Foundation: {final_result['source_data']['organization_name'] or 'Unknown'}")
    print(f"📊 Grants Processed: {final_result['pipeline_info']['grants_processed']}")
    print(f"🎯 Grant Programs: {', '.join(final_result['source_data']['grant_names'])}")
    print(f"📝 Description Length: {len(final_result['grant_opportunity_description'].split())} words")
    print(f"🏷️ Metadata Fields: {len(final_result['grant_metadata'])} fields generated")
    
    # Save consolidated result to JSON file
    output_filename = "consolidated_grant_result.json"
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Consolidated result saved to: {output_filename}")
    except Exception as e:
        print(f"❌ Error saving consolidated result: {e}")
    
    # Also save individual components for reference
    try:
        # Save grant description
        with open("grant_description.md", 'w', encoding='utf-8') as f:
            f.write(final_result['grant_opportunity_description'])
        
        # Save metadata
        with open("grant_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(final_result['grant_metadata'], f, indent=4, ensure_ascii=False)
            
        print(f"📁 Individual files saved:")
        print(f"   - grant_description.md")
        print(f"   - grant_metadata.json")
        
    except Exception as e:
        print(f"⚠️ Error saving individual files: {e}")
    
    print(f"\n✅ COMPLETE PIPELINE FINISHED SUCCESSFULLY!")
    print("🎉 All 4 steps completed - consolidated JSON result ready!")
    
    return final_result


if __name__ == "__main__":
    main()