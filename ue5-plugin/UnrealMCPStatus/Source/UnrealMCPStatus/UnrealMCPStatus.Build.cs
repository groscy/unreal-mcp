// Copyright unreal-mcp. Source-distributed UE5 editor plugin.

using UnrealBuildTool;

public class UnrealMCPStatus : ModuleRules
{
	public UnrealMCPStatus(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
			}
		);

		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"CoreUObject",
				"Engine",
				"Sockets",
				"Networking",
				"Json",
				"Slate",
				"SlateCore",
				"ToolMenus",
				"LevelEditor",
			}
		);
	}
}
