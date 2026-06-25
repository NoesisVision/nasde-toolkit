// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';
import starlightLinksValidator from 'starlight-links-validator';
import starlightLlmsTxt from 'starlight-llms-txt';

// https://astro.build/config
export default defineConfig({
	site: 'https://noesisvision.github.io',
	base: '/nasde-toolkit/',
	integrations: [
		mermaid(),
		starlight({
			title: 'Nasde Toolkit Docs',
			logo: {
				src: './src/assets/nasde-mark.png',
				alt: 'Nasde Toolkit',
			},
			favicon: '/favicon.png',
			customCss: ['./src/styles/custom.css'],
			components: {
				SocialIcons: './src/components/HeaderNav.astro',
			},
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/NoesisVision/nasde-toolkit' },
				{ icon: 'discord', label: 'Discord', href: 'https://discord.gg/QF5PMX4Dqg' },
			],
			plugins: [starlightLinksValidator(), starlightLlmsTxt()],
			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Overview', slug: 'getting-started/overview' },
						{ label: 'Quick Start', slug: 'getting-started/quick-start' },
						{ label: 'Reading Your Results', slug: 'getting-started/reading-results' },
					],
				},
				{
					label: 'Concepts',
					items: [
						{ label: 'How It Works', slug: 'concepts/how-it-works' },
						{ label: 'Key Terms', slug: 'concepts/key-terms' },
						{ label: 'A Real Task (DDD example)', slug: 'concepts/real-task-example' },
						{ label: 'Token & Cost', slug: 'concepts/token-cost' },
						{ label: 'Calibrating the Rubric', slug: 'concepts/calibration' },
					],
				},
				{
					label: 'Creating Benchmarks',
					items: [
						{ label: 'Anatomy of a Benchmark', slug: 'creating-benchmarks/anatomy' },
						{ label: 'Assessment Criteria & Dimensions', slug: 'creating-benchmarks/assessment-criteria' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'CLI Reference', slug: 'reference/cli-reference' },
						{ label: 'Configuration', slug: 'reference/configuration' },
						{ label: 'Authentication & Opik', slug: 'reference/authentication' },
					],
				},
				{
					label: 'Guides',
					items: [
						{ label: 'Running & Configuring Runs', slug: 'guides/running-benchmarks' },
						{ label: 'Plugins & Skills', slug: 'guides/plugins-and-skills' },
						{ label: 'Use Cases (end-to-end)', slug: 'guides/use-cases' },
						{ label: 'Benchmark Results', slug: 'guides/benchmark-results' },
						{ label: 'Troubleshooting & FAQ', slug: 'guides/troubleshooting' },
					],
				},
			],
		}),
	],
});
