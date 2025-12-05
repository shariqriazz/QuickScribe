#!/usr/bin/env python3
"""
Model audio validation tool.
Tests text and audio input validation for multiple models in parallel.
"""
import sys
import argparse
import concurrent.futures
import re
from colorama import Fore, Style, init
from config_manager import ConfigManager
from providers.base_provider import BaseProvider

init(autoreset=True)


class MockAudioProcessor:
    """Mock audio processor for testing."""
    pass


def test_model(model_id: str, debug_level: int = 0) -> dict:
    """
    Test a single model's text and audio validation.

    Returns:
        dict: {
            'model_id': str,
            'overall_success': bool,
            'text_passed': bool,
            'text_error': str or None,
            'audio_passed': bool,
            'audio_error': str or None,
            'combined_passed': bool,
            'combined_error': str or None,
            'intelligence_result': str or None
        }
    """
    print(f"\n[{model_id}] Starting validation...")

    try:
        config = ConfigManager()
        config.model_id = model_id
        config.litellm_debug = debug_level >= 2
        config.audio_source = 'raw'
        config.mode = 'dictate'

        provider = BaseProvider(config, MockAudioProcessor())

        success = provider.initialize()

        if provider.validation_results:
            result = provider.validation_results.copy()
            result['model_id'] = model_id
        else:
            result = {
                'model_id': model_id,
                'overall_success': success
            }

        return result

    except Exception as e:
        error_type = type(e).__name__
        error_msg = f"{error_type}: {str(e)}"
        print(f"\n{Fore.RED}✗ {model_id} - {error_msg}{Style.RESET_ALL}")
        return {
            'model_id': model_id,
            'overall_success': False,
            'error': error_msg
        }


def main():
    parser = argparse.ArgumentParser(
        description='Validate text and audio input for multiple models in parallel'
    )
    parser.add_argument(
        'models',
        nargs='+',
        help='Model IDs to test (format: provider/model or openrouter/provider/model)'
    )
    parser.add_argument(
        '--debug', '-d',
        action='count',
        default=0,
        help='Debug level (-d for basic, -dd for LiteLLM debug)'
    )

    args = parser.parse_args()
    models = args.models
    debug_level = args.debug

    print(f"Testing {len(models)} model(s) in parallel...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {executor.submit(test_model, model, debug_level): model for model in models}
        results = []

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)

    results.sort(key=lambda x: x['model_id'])

    print("\n" + "="*60)
    print("RESULTS SUMMARY:")
    print("="*60)

    overall_passed = 0
    overall_failed = 0

    text_passed = 0
    audio_passed = 0
    combined1_passed = 0
    combined2_passed = 0

    for result in results:
        model_id = result['model_id']
        overall_success = result.get('overall_success', False)

        if overall_success:
            print(f"{Fore.GREEN}✓{Style.RESET_ALL} {model_id}")
            overall_passed += 1
        else:
            print(f"{Fore.RED}✗{Style.RESET_ALL} {model_id}")
            overall_failed += 1
            if 'error' in result:
                print(f"  Error: {result['error']}")
                continue

        # Display segmented results
        if result.get('text_passed'):
            text_passed += 1
            status = f"{Fore.GREEN}✓{Style.RESET_ALL}"
        else:
            status = f"{Fore.RED}✗{Style.RESET_ALL}"
        print(f"  Text validation (1+1): {status}")
        if result.get('text_response'):
            if re.search(r'\b2\b|two', result['text_response'], re.IGNORECASE):
                print(f"    Intelligence: {Fore.GREEN}✓ Got: {result['text_response'][:100]}{Style.RESET_ALL}")
            else:
                print(f"    Intelligence: {Fore.YELLOW}⚠ Expected '2' but got: {result['text_response'][:100]}{Style.RESET_ALL}")

        if result.get('audio_passed'):
            audio_passed += 1
            status = f"{Fore.GREEN}✓{Style.RESET_ALL}"
        else:
            status = f"{Fore.RED}✗{Style.RESET_ALL}"
        print(f"  Audio validation (sumtest.wav): {status}")
        if result.get('audio_response'):
            if re.search(r'\b2\b|two', result['audio_response'], re.IGNORECASE):
                print(f"    Intelligence: {Fore.GREEN}✓ Got: {result['audio_response'][:100]}{Style.RESET_ALL}")
            else:
                print(f"    Intelligence: {Fore.YELLOW}⚠ Expected '2' but got: {result['audio_response'][:100]}{Style.RESET_ALL}")

        if result.get('combined1_passed'):
            combined1_passed += 1
            status = f"{Fore.GREEN}✓{Style.RESET_ALL}"
        else:
            status = f"{Fore.RED}✗{Style.RESET_ALL}"
        print(f"  Combined (text '1+1' + silence): {status}")
        if result.get('combined1_response'):
            if re.search(r'\b2\b|two', result['combined1_response'], re.IGNORECASE):
                print(f"    Intelligence: {Fore.GREEN}✓ Got: {result['combined1_response'][:100]}{Style.RESET_ALL}")
            else:
                print(f"    Intelligence: {Fore.YELLOW}⚠ Expected '2' but got: {result['combined1_response'][:100]}{Style.RESET_ALL}")

        if result.get('combined2_passed'):
            combined2_passed += 1
            status = f"{Fore.GREEN}✓{Style.RESET_ALL}"
        else:
            status = f"{Fore.RED}✗{Style.RESET_ALL}"
        print(f"  Combined (audio + 'compute value'): {status}")
        if result.get('combined2_response'):
            if re.search(r'\b2\b|two', result['combined2_response'], re.IGNORECASE):
                print(f"    Intelligence: {Fore.GREEN}✓ Got: {result['combined2_response'][:100]}{Style.RESET_ALL}")
            else:
                print(f"    Intelligence: {Fore.YELLOW}⚠ Expected '2' but got: {result['combined2_response'][:100]}{Style.RESET_ALL}")

        print()

    print("="*60)
    print(f"Overall: {overall_passed}/{len(models)} models passed all tests")
    print(f"Text (1+1): {text_passed}/{len(models)} passed")
    print(f"Audio (sumtest.wav): {audio_passed}/{len(models)} passed")
    print(f"Combined (text+silence): {combined1_passed}/{len(models)} passed")
    print(f"Combined (audio+prompt): {combined2_passed}/{len(models)} passed")
    print("="*60)

    sys.exit(0 if overall_failed == 0 else 1)


if __name__ == '__main__':
    main()
